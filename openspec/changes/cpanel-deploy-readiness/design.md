## Context

Shorty is a FastAPI application using `uv` for dependency management and `pydantic-settings` for configuration. cPanel's Application Manager uses Phusion Passenger as the application server. Passenger expects:

1. A `passenger_wsgi.py` file in the application root that exports a WSGI/ASGI `application` callable
2. A Python virtual environment (standard PEP 405 layout)
3. Dependencies installable via `pip install -r requirements.txt` (for the "Ensure Dependencies" UI button)
4. Restarts triggered by touching `tmp/restart.txt`

The application currently uses `uv run shorty` (uvicorn) for local development. In production under Passenger, uvicorn is not needed — Passenger is both the process manager and the reverse proxy.

cPanel's Application Manager sets environment variables via Apache `SetEnv` directives. pydantic-settings reads these as OS-level environment variables with higher priority than `.env` file values, so the existing `Settings` class works without modification.

## Goals / Non-Goals

**Goals:**
- Provide a `passenger_wsgi.py` entrypoint compatible with cPanel's Phusion Passenger
- Generate a `requirements.txt` so cPanel can install dependencies via its UI or CLI
- Document the complete deploy process: cPanel Application Manager, MySQL, Redis, migrations

**Non-Goals:**
- Automate deploy via CI (no CI infrastructure configured per project charter)
- Create Dockerfile or docker-compose.yml (explicitly excluded by project conventions)
- Modify application source code
- Add health-check endpoints (separate concern)

## Decisions

### Entrypoint: `passenger_wsgi.py` at project root

cPanel's Application Manager expects the startup file path relative to the home directory (e.g., `shorty/passenger_wsgi.py`). Placing it at the repo root keeps the cPanel "Application Path" configuration simple.

The file uses the `os.execl` trick (from cPanel's official docs) to re-execute itself under the venv Python, ensuring all dependencies are available when Passenger loads the script with the system Python.

```python
import sys, os
INTERP = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python3")
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)
sys.path.insert(0, os.path.dirname(__file__))
from src.api.main import app as application
```

### `requirements.txt` generated from `pyproject.toml`

`uv pip compile` converts the PEP 621 dependency list to a pip-compatible `requirements.txt`. This file is committed to the repo so cPanel's "Ensure Dependencies" button can use it directly. It is regenerated whenever dependencies change.

Alternative considered: Using `uv sync` manually via SSH. This works but bypasses cPanel's UI. Generating `requirements.txt` supports both workflows.

### Environment variables via cPanel UI

The Application Manager UI lets you set environment variables that become Apache `SetEnv` directives. pydantic-settings reads these natively. The `.env` file remains for local development and serves as documentation of required variables. In production, cPanel env vars take precedence.

Required variables for production:
- `DATABASE_URL` — MySQL connection string
- `REDIS_URL` — Upstash Redis connection string
- `SHORT_BASE_URL` — public URL of the API subdomain
- `SNOWFLAKE_NODE_ID` — worker ID (0 for single-instance)
- `CORS_ORIGIN` — frontend origin URL

### Passenger handles the ASGI lifecycle

FastAPI's `lifespan` context manager (startup/shutdown, background cleanup loop) works under Passenger because Passenger manages the Python process lifecycle. The cleanup loop runs as an `asyncio` task within the Passenger-managed process. No external process manager (systemd, supervisord) is needed.

## Risks / Trade-offs

- [Python version mismatch] The hosting provider's Passenger may use a system Python older than 3.12. If the host doesn't offer 3.12, the `requires-python = ">=3.12"` constraint must be relaxed and compatibility verified. Mitigation: cPanel on AlmaLinux 9+ ships Python 3.12 via AppStream.
- [aiomysql edge cases] aiomysql is pure Python so it has no C-extension risks on shared hosting. However, MySQL connection pooling behaves differently than psycopg2/asyncpg. The existing SQLAlchemy async session factory handles this correctly.
- [Redis connectivity] Upstash requires outbound TLS on port 6379/6380. Some shared hosts firewall non-standard ports. Mitigation: Upstash supports port 443 (HTTPS) for Redis clients. Use `rediss://...:443` if standard ports are blocked.
- [Cold starts] Passenger may idle the process under zero traffic. First request after idle will be slow (Python import + DB connection). Acceptable for a small project; no mitigation needed.
