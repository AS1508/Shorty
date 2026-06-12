## Context

Shorty es una API FastAPI con MYSQL/Redis, autenticación delegada a proxy (HMAC sobre `X-Authenticated-User`), y dos endpoints: `POST /Create-URL` (protegido) y `GET /{short_code}` (público). Ya existe un `RedisCache` con `get` y `set` usado para caché de resolución de URLs. La arquitectura organiza la lógica de negocio en `src/core/`, la infraestructura en `src/infra/`, y las rutas en `src/api/routes/`. Las dependencias cross-cutting (auth, DB sessions, use cases) se inyectan vía `Depends` de FastAPI desde `src/api/dependencies.py`.

No existe actualmente ningún rate limiting. La necesidad surge de dos vectores de abuso: saturación de la DB por creación masiva de URLs, y scraping del espacio de short codes vía fuerza bruta en `GET /{code}`.

## Goals / Non-Goals

**Goals:**

- Limitar creación de URLs por usuario autenticado (email) usando ventana fija en Redis.
- Limitar requests de redirección por IP usando ventana fija en Redis.
- Responder con HTTP 429 + `Retry-After` al exceder cualquier límite.
- Fail-open: si Redis no responde, se permite la request y se loggea un warning.
- Configuración vía variables de entorno con valores por defecto razonables.
- Resolver la IP real del cliente detrás de un reverse proxy (X-Forwarded-For).

**Non-Goals:**

- Sliding window, token bucket, o leaky bucket (innecesario para este caso de uso).
- Rate limiting en `/docs` u otros endpoints internos.
- Bloqueo permanente (ban) de IPs o usuarios.
- Whitelist/blacklist.
- Rate limiting por IP en creación o por usuario en redirección.
- Dashboard o métricas de rate limiting.

## Decisions

### 1. Algoritmo: ventana fija con INCR + EXPIRE

```
INCR  rate:<scope>:<key>:<window_ts>   → N
EXPIRE rate:<scope>:<key>:<window_ts> <window_seconds>
IF N > limit → 429
```

**Alternativas consideradas:**

| Algoritmo | Ventaja | Desventaja | Veredicto |
|-----------|---------|------------|-----------|
| Fixed window | Simple, atómico (INCR), 1-2 comandos Redis | Boundary burst (~2x en borde) | **Elegido** — el burst es aceptable |
| Sliding window (ZSET) | Preciso, sin burst | Múltiples operaciones Redis, requiere Lua para atomicidad | Rechazado — complejidad innecesaria |
| Token bucket | Rate suave, permite bursts controlados | Requiere estado de tokens y timestamps, Lua script | Rechazado — overengineering |

**Racional:** La ventana fija ofrece la mejor relación simplicidad/eficacia. El boundary burst (40 creaciones en ~2 minutos en el peor caso) no representa un riesgo real de saturación de la DB. Redis `INCR` es atómico por diseño — no se requiere Lua scripting.

**EXPIRE en cada request vs solo en la primera:** Llamar `EXPIRE` en cada request es idempotente y evita el race condition de "INCR retorna 1 → EXPIRE". Si el proceso muere entre INCR y EXPIRE cuando solo se llama en la primera, la clave nunca expira. Con EXPIRE siempre, el TTL se refresca pero eso no afecta el contador (la ventana ya está determinada por el timestamp en la key).

### 2. Ubicación: dependencias de FastAPI (no middleware)

Las dependencias (`Depends`) se integran en el pipeline de FastAPI antes del handler, permiten inyectar el objeto `Request`, y siguen el patrón existente del proyecto (`require_authenticated_user`, `get_session`, etc.).

**Alternativa rechazada — ASGI middleware:** Requeriría cambios en `src/api/main.py`, acceso manual a headers, y tipado más débil. No se justifica para rate limiting selectivo (diferentes claves y límites por endpoint).

**Flujo resultante:**

```
POST /Create-URL:
  Request → AuthDep → RateLimitDep(create) → Handler → Response
                          │
                          ├─ Redis OK, N ≤ limit → next()
                          ├─ Redis OK, N > limit → HTTPException(429)
                          └─ Redis error        → next() + log warning

GET /{short_code}:
  Request → RateLimitDep(redirect) → Handler → Response
                │
                ├─ Redis OK, N ≤ limit → next()
                ├─ Redis OK, N > limit → HTTPException(429)
                └─ Redis error        → next() + log warning
```

### 3. Nuevo método `incr` en RedisCache

`RedisCache` actualmente expone `get` y `set`. Se agrega `incr(key: str) -> int | None` que:
- Llama `INCR key` en Redis.
- Retorna el nuevo valor del contador.
- Retorna `None` en caso de error (ConnectionError u otros), permitiendo fail-open.
- No maneja TTL — el llamante aplica `EXPIRE` por separado vía `set` o un nuevo método helper.

Se evaluó agregar un método combinado `incr_with_expire(key, ttl) -> int | None` que haga INCR + EXPIRE atómicamente, pero Redis no expone un comando atómico para esto sin Lua. Dos comandos secuenciales con EXPIRE idempotente son suficientes.

### 4. Resolución de IP real

```
def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()  # último proxy de confianza
    return request.client.host if request.client else "unknown"
```

Se toma el **último** valor de `X-Forwarded-For` porque el proxy de confianza (único, típicamente nginx/Caddy) appende la IP del cliente al final de la lista. Si no hay header, se usa `request.client.host`. Para IPv6 se usa la representación comprimida estándar.

**Alternativa rechazada — `X-Real-IP`:** Menos estándar, no soportado por todos los proxies.

### 5. Formato de claves Redis

```
rate:create:{quote(email)}:{window_ts}
rate:redirect:{ip}:{window_ts}
```

`window_ts = (now_seconds // window_seconds) * window_seconds` (piso de la ventana). El email se URL-encodea para manejar caracteres como `+`. Las IPs IPv6 se usan tal cual (los `:` son válidos en keys de Redis, pero para evitar ambigüedad visual se normalizan a formato comprimido).

### 6. Fail-open

Cualquier excepción de Redis (`ConnectionError`, `TimeoutError`, etc.) se captura, se loggea un warning, y se permite la request. Esto es consistente con el comportamiento actual del `RedisCache` (`get` retorna `None`, `set` loggea y sigue). Sin Redis no hay rate limiting, pero el servicio sigue operativo.

### 7. Respuesta 429

```json
HTTP/1.1 429 Too Many Requests
Retry-After: <segundos_restantes_en_la_ventana>
Content-Type: application/json

{"detail": "Rate limit exceeded. Try again in X seconds."}
```

`X` = `window_seconds - (now_seconds % window_seconds)`, es decir, los segundos que faltan para que la ventana actual termine y el contador se reinicie.

### 8. Configuración

Campos nuevos en `Settings` (Pydantic):

| Campo | Default | Descripción |
|-------|---------|-------------|
| `rate_limit_create_count` | `20` | Máximo de URLs creadas por usuario en la ventana |
| `rate_limit_create_window_seconds` | `3600` | Duración de la ventana para creación (1 hora) |
| `rate_limit_redirect_count` | `100` | Máximo de redirects por IP en la ventana |
| `rate_limit_redirect_window_seconds` | `60` | Duración de la ventana para redirección (1 minuto) |

## Risks / Trade-offs

- **[Boundary burst]** Un usuario puede hacer hasta ~2x el límite si opera justo en el borde de la ventana (ej. 20 URLs a las 10:59 + 20 a las 11:00 = 40 en ~2 min). **Mitigación**: Aceptado como trade-off de simplicidad. 40 inserts no saturan la DB.
- **[NAT / CGNAT]** Múltiples usuarios detrás de una misma IP pública comparten el límite de redirección. **Mitigación**: El límite por defecto (100/min) es lo suficientemente alto para cubrir una oficina pequeña. Si es un problema, se puede aumentar vía variable de entorno.
- **[Spoofing de X-Forwarded-For]** Si el proxy de confianza no pisa el header, un atacante puede elegir su IP. **Mitigación**: Se documenta que el proxy DEBE configurarse para sobreescribir `X-Forwarded-For`. La extracción toma el último valor de la lista, asumiendo un proxy de confianza.
- **[Redis caído = sin rate limiting]** Si Redis está inalcanzable, el rate limiting desaparece pero el servicio sigue. **Mitigación**: El fail-open es deliberado — prioriza disponibilidad sobre protección. Se loggea un warning para alertar a operaciones.
- **[Sin diferenciación entre tipos de respuesta en redirect]** Los 404, 403, y 410 también consumen quota del rate limit de IP. Un atacante que solo recibe 404s igual gasta su límite. **Mitigación**: Comportamiento intencional — el rate limiting se aplica antes de resolver, por lo que no se distingue el resultado.
