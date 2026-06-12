## Why

Actualmente Shorty no tiene ningún mecanismo de rate limiting. Un usuario autenticado puede crear miles de URLs en minutos saturando la base de datos, y un atacante puede hacer scraping masivo del espacio de short codes vía `GET /{code}` sin freno alguno. Agregar rate limiting en dos capas —creación por usuario y redirección por IP— cierra estos vectores de abuso usando la infraestructura Redis ya existente, sin nuevos servicios y con fail-open.

## What Changes

- Nueva dependencia de rate limiting para `POST /Create-URL`: limita a **N URLs por ventana de T segundos** por usuario autenticado (email). Por defecto 20/hora.
- Nueva dependencia de rate limiting para `GET /{short_code}`: limita a **M requests por ventana de S segundos** por IP del cliente. Por defecto 100/minuto.
- Cuando un límite se excede, el sistema responde con HTTP **429 Too Many Requests**, header `Retry-After` con los segundos restantes, y no ejecuta el handler.
- Si Redis está caído, el rate limiter hace **fail-open**: loggea un warning y permite la request.
- Nuevas variables de entorno configurables: `RATE_LIMIT_CREATE_COUNT`, `RATE_LIMIT_CREATE_WINDOW_SECONDS`, `RATE_LIMIT_REDIRECT_COUNT`, `RATE_LIMIT_REDIRECT_WINDOW_SECONDS`.
- Resolución de IP real del cliente respetando el header `X-Forwarded-For` (confía en el último proxy de la cadena).

## Capabilities

### New Capabilities

- `rate-limiting`: Lógica de rate limiting con ventana fija respaldada por Redis. Incluye contadores atómicos (`INCR`), TTL por ventana, cálculo de `Retry-After`, extracción de IP real, y fail-open.

### Modified Capabilities

- `url-shortening`: El endpoint `POST /Create-URL` ahora puede responder **429 Too Many Requests** cuando el usuario autenticado excede el límite de creación. Esta respuesta se genera antes del handler (en la capa de dependencias) y no escribe en la base de datos.
- `url-redirection`: El endpoint `GET /{short_code}` ahora puede responder **429 Too Many Requests** cuando la IP del cliente excede el límite de redirección. Esta respuesta se genera antes del handler y no consulta Redis ni la base de datos.

## Impact

- `src/api/dependencies.py`: nuevas dependencias `RateLimitCreateDep` y `RateLimitRedirectDep`; acceso al objeto `Request` para leer IP.
- `src/api/routes/shortener.py`: se inyecta `RateLimitCreateDep` en el handler de `POST /Create-URL`.
- `src/api/routes/redirect.py`: se inyecta `RateLimitRedirectDep` en el handler de `GET /{short_code}`.
- `src/infra/config.py`: nuevos campos `rate_limit_create_count`, `rate_limit_create_window_seconds`, `rate_limit_redirect_count`, `rate_limit_redirect_window_seconds`.
- `src/infra/cache/redis.py`: nuevo método `incr` en `RedisCache` (con fail-open).
- Nuevo módulo `src/core/rate_limit.py` con la lógica de ventana fija.
- Tests: `tests/unit/test_rate_limit.py`, `tests/integration/test_rate_limit_endpoints.py`.
