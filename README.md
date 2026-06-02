# Shorty

A minimal URL shortener: `POST /Create-URL` with a long URL, get back a short alias. Built with FastAPI, Snowflake IDs, Base62 encoding, and PostgreSQL.

## Prerequisites

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/) for Python dependency management
- A PostgreSQL 14+ instance reachable via `DATABASE_URL` (any modern Postgres works)

## Setup

```bash
uv sync
```

## Configuration

The service reads the following environment variables (with defaults):

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://shorty:shorty@localhost:5432/shorty` | SQLAlchemy async URL for the application database. |
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

## Tests

```bash
uv run pytest
```

Unit tests cover the Base62 codec, the Snowflake generator (uniqueness, sequence exhaustion, clock-drift detection), and the `CreateShortURL` use case. Integration tests run the FastAPI app against an in-memory SQLite database.

## Development

```bash
uv run ruff check src tests   # lint
uv run mypy src tests         # type check
uv run pytest                 # tests
```
