## Why

The Shorty service has no production code yet — only a hello-world `main.py`. To deliver value, the first user-facing capability is shortening a long URL into a compact alias. This change introduces the minimal viable endpoint to ingest a long URL, persist it, and return a short code that can later be resolved by a follow-up redirect endpoint (out of scope here).

## What Changes

- Add `POST /Create-URL` HTTP endpoint that accepts a JSON body `{"url": "<long-url>"}` and returns `201 Created` with `{"short_url": "https://<host>/<code>"}`.
- Implement an in-process **Snowflake ID generator** (64-bit: 41 bits timestamp + 10 bits node + 12 bits sequence) that produces unique, monotonic IDs without DB round-trips.
- Implement **Base62 encode/decode** to convert the numeric Snowflake ID into a short alphanumeric code.
- Validate input URLs (must parse, must include scheme, max 2048 chars) and reject malformed payloads with `400 Bad Request`.
- Persist records in PostgreSQL with the columns `id` (BIGINT, Snowflake), `original_url` (TEXT), `created_at` (TIMESTAMPTZ).
- Handle Snowflake edge cases: sequence exhaustion within a millisecond (block until next ms) and clock drift backwards (raise `InvalidSystemClock`).
- Return `500` if persistence fails; never return a short URL whose row was not actually written.
- Add unit tests for Base62, Snowflake uniqueness, and clock drift; add an integration test for the endpoint against an ephemeral database.

## Capabilities

### New Capabilities

- `url-shortening`: The capability to accept a long URL, generate a unique short code, persist the mapping, and return the short URL. Covers the `POST /Create-URL` endpoint, Snowflake ID generation, Base62 encoding, input validation, and persistence.

### Modified Capabilities

_None — this is the first capability introduced in the repo._

## Impact

- **New code paths:** `src/api/routes/shortener.py`, `src/core/snowflake.py`, `src/core/base62.py`, `src/infra/db/models.py`, `src/infra/db/repository.py`.
- **New dependencies:** `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `pytest`, `pytest-asyncio`, `httpx`, `mypy`.
- **Database:** adds a new `urls` table; no migrations exist yet, so the first migration (Alembic) is bootstrapped as part of this change.
- **API contract:** introduces a new public endpoint; no existing clients to break.
- **Out of scope (explicit):** the redirect endpoint (`GET /{short_code}`), TTL/expiration, custom aliases, authentication, rate limiting, analytics.
