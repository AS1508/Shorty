## Why

The service can create short URLs but cannot resolve them — there is no `GET /{short_code}` handler. Without a redirect endpoint the shortener does nothing useful. This change implements the read path: decode the short code, look up the original URL (cached + DB), and redirect the client.

## What Changes

- Add `GET /{short_code}` endpoint that decodes the Base62 code to a Snowflake ID, resolves the original URL, and responds with HTTP 302 `Location: <url>`.
- Add a Redis-backed cache layer for URL lookups with positive TTL and negative caching (store a sentinel for non-existent IDs to reduce DB load on 404 attacks).
- Read from cache (fast path) → fall back to PostgreSQL (slow path) → populate cache on miss.
- Handle edge cases: non-existent code (404), expired/deleted record (410), blocked/malicious URL (403), and Redis connection failure (graceful degradation — skip cache, read DB directly).
- Add `redis-py` dependency and a `redis://` connection string to settings.
- Add unit/integration tests for the cache-adapter, DB read, and the full redirect flow.

## Capabilities

### New Capabilities

- `url-redirect`: The capability to resolve a short URL code returned by `POST /Create-URL`. Covers the `GET /{short_code}` endpoint, Base62 decode, cache-or-DB resolution, and redirect/error responses.

### Modified Capabilities

_None — the existing `url-shortening` spec is write-only and doesn't need revision._

## Impact

- **New code paths:** `src/api/routes/redirect.py`, `src/core/usecases/resolve_url.py`, `src/infra/cache/redis.py`.
- **New dependencies:** `redis-py` (async via `redis.asyncio`).
- **New settings env vars:** `REDIS_URL` (default `redis://localhost:6379/0`).
- **Modified existing:** `src/infra/db/repository.py` (add `find_by_id(id) -> UrlRecord | None`), `src/core/ports.py` (add `UrlRepository.find_by_id`), `src/api/main.py` (wire Redis client), `src/infra/config.py` (add `REDIS_URL`).
- **Out of scope:** Analytics event publishing (a future queue/worker change), admin flags (`is_blocked`, TTL expiration), dashboard UI.
