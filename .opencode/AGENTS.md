## Tech Stack
  - Python/FastAPI
  - Typescript/React/Vite
  - PostgreSQL/Redis
  - uv(Gestor de paquetes Backend)/npm(Gestor de paquetes Frontend)

## Patterns
  - Arquitectura: Usar Arquitectura Hexagonal (o Clean Architecture). Separar controladores, casos de uso y repositorios.

  - Manejo de Errores: Usar HTTPException en FastAPI con códigos de estado semánticos y mensajes claros. Retornar temprano (early returns).

  - Tipado: Tipado estricto obligatorio. Nada de tipos inferidos implícitamente en parámetros de funciones.

  - Asincronismo: Usar siempre async/await, prohibido el uso de callbacks tradicionales.

## Forbids
  - PROHIBIDO usar any (si es TypeScript) o ignorar el tipado estricto.

  - PROHIBIDO exponer secretos, contraseñas o tokens en el código fuente (usar siempre variables de entorno).

  - PROHIBIDO dejar bloques de código con // ... resto del código. Debes escribir la implementación completa o pedir confirmación antes de truncar.

  - PROHIBIDO modificar configuraciones de infraestructura (Dockerfile, docker-compose.yml) a menos que el usuario lo solicite explícitamente.

## Project Structure
  - src/api/: Controladores y definición de rutas.
  
  - src/core/: Casos de uso y lógica de negocio (Snowflake, Base62).
  
  - src/infra/: Adaptadores de base de datos, caché (Redis) y configuraciones.
  
  - tests/: Archivos de prueba separados por unidad e integración.

## WorkFlow
1. Exploración y Contexto (Analyze)
Lee la especificación de la tarea (issue, ticket o prompt del usuario).
Explora la base de código actual para entender el contexto (app/api/, app/core/, etc.).
Revisa las dependencias actuales usando uv (backend) o package.json (frontend) para no reinventar la rueda.

2. Planificación y Aprobación (Plan & Ask)
Antes de escribir una sola línea de código, redacta un plan breve (3-4 viñetas) explicando qué archivos se van a crear o modificar.
Detente y pide confirmación al usuario. No comiences a codificar hasta recibir un "ok" explícito.

3. Ejecución (Code)
Escribe el código respetando el stack tecnológico y las prohibiciones (ej. usar async/await en FastAPI).
Mantén los cambios pequeños y enfocados en el alcance de la tarea. No refactorices código ajeno al ticket a menos que se te pida.

4. Verificación Local (Test & Lint)
Escribe o actualiza las pruebas en pytest (backend) o Vitest/Jest (frontend).
Ejecuta los tests localmente. Si los tests fallan, el agente debe intentar arreglarlos de forma autónoma hasta 3 veces antes de pedir ayuda al usuario.
Verifica que el código cumpla con las reglas de tipado estricto (mypy/TypeScript).

5. Cierre y Registro (Document & Commit)
Si la tarea implica un cambio en la API, actualiza la especificación o el archivo de documentación correspondiente.
Realiza el commit usando Conventional Commits (ej. feat: add snowflake id generator).
Informa al usuario que la tarea está terminada y lista para revisión.
Si modificas un modelo de la base de datos (PostgreSQL), debes generar el archivo de migración correspondiente (ej. usando Alembic).
