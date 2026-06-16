## Why

The backend is feature-complete and tested, but lacks the entrypoint file (`passenger_wsgi.py`) and dependency manifest (`requirements.txt`) required by cPanel's Phusion Passenger to serve the application. Without these, the app cannot be deployed to any cPanel-based shared hosting environment.

## What Changes

- **`passenger_wsgi.py`**: New ASGI entrypoint that re-executes the script under the venv Python and exports `app` as `application` for Phusion Passenger.
- **`requirements.txt`**: Generated dependency manifest so cPanel's "Ensure Dependencies" button can install packages.
- **`tmp/restart.txt`**: Placeholder file. Touching it triggers Passenger to restart the application on next request (standard Passenger mechanism).
- **`DEPLOY.md`**: Step-by-step deploy guide covering cPanel Application Manager, environment variables, MySQL setup, Redis (Upstash), Alembic migrations, and verification.

No breaking changes. No application code modifications.

## Capabilities

### New Capabilities

- `cpanel-deploy`: The application can be registered and served via cPanel's Application Manager with Phusion Passenger, reading configuration from environment variables and connecting to MySQL and Redis.

### Modified Capabilities

*(None.)*

## Impact

- **New files**: `passenger_wsgi.py`, `requirements.txt`, `tmp/restart.txt`, `DEPLOY.md` — all at project root
- **Modified files**: None
- **Dependencies**: None
- **Infrastructure**: Requires cPanel with `ea-apache24-mod-passenger` and `ea-apache24-mod_env`, MySQL database, and an external Redis instance (e.g., Upstash)
