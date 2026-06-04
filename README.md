# Shorty

A minimal URL shortener: `POST /Create-URL` with a long URL, get back a short alias. `GET /{short_code}` resolves the alias via a Redis cache (with MySQL fallback) and redirects the client. Built with FastAPI, Snowflake IDs, and Base62 encoding.

## Prerequisites

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/) for Python dependency management
- A MySQL 8+ instance reachable via `DATABASE_URL`
- A Redis 6+ instance reachable via `REDIS_URL` (optional in development — the service falls back to DB-only)

## Setup

```bash
uv sync
```

## Configuration

The service reads the following environment variables (with defaults):

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `mysql+aiomysql://shorty:shorty@localhost:3306/shorty` | SQLAlchemy async URL for the application database. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL used for the read cache layer. |
| `SHORT_BASE_URL` | `http://localhost:8000` | Public base URL prepended to generated short codes. |
| `SNOWFLAKE_NODE_ID` | `0` | Worker ID embedded in generated Snowflake IDs (integer in `[0, 1023]`). |

## Run migrations

```bash
uv run alembic upgrade head
```

## Start the service

```bash
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

Or use the installed script:

```bash
uv run shorty
```

## API

### `POST /Create-URL`

Request:

```bash
curl -X POST http://localhost:8000/Create-URL \
  -H 'content-type: application/json' \
  -d '{"url": "https://www.example.com/some/long/path"}'
```

Response (HTTP 201):

```json
{
  "short_url": "http://localhost:8000/NdEmeHuf0C"
}
```

Validation failures (missing field, non-string value, URL without `http://`/`https://` scheme, URL longer than 2048 characters) return HTTP 400 with `{"detail": "<message>"}`. Persistence or server failures return HTTP 500.

### `GET /{short_code}`

Request:

```bash
curl -L http://localhost:8000/NdEmeHuf0C
```

Response (HTTP 302):

```
HTTP 302 Found
Location: https://www.example.com/some/long/path
```

Error responses:
- **400** — short code contains invalid characters (non-Base62).
- **403** — the URL has been blocked (`is_blocked = true` in the database).
- **404** — the short code does not match any stored record.

## Tests

```bash
uv run pytest
```

Unit tests cover the Base62 codec, the Snowflake generator (uniqueness, sequence exhaustion, clock-drift detection), the `CreateShortURL` and `ResolveURL` use cases, and the Redis cache adapter graceful-degradation path. Integration tests run the FastAPI app against an in-memory SQLite database with a fake cache.

## Development

```bash
uv run ruff check src tests   # lint
uv run mypy src tests         # type check
uv run pytest                 # tests
```
