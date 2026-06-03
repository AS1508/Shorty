## Context

The service currently only writes URLs (POST /Create-URL). The redirect endpoint is the other half of the shortener contract: given the short code, return the original URL as an HTTP redirect. A cache layer (Redis) is required to absorb read traffic without hitting PostgreSQL on every request.

The hexagonal layout is established:
```
src/api/       → routes, schemas
src/core/      → use cases, ports, snowflake, base62
src/infra/db/  → SQLAlchemy model + repository
src/infra/     → new: cache adapter (redis)
```

## Goals / Non-Goals

**Goals:**
- Implement `GET /{short_code}` with HTTP 302 redirect on success.
- Cache resolved URLs in Redis (positive TTL: 1 hour default).
- Negative-cache non-existent IDs (sentinel, TTL: 30 seconds) to absorb 404 bombardment.
- Fall back to PostgreSQL on cache miss; populate cache on return.
- Gracefully degrade (skip cache, read DB) when Redis is unreachable.
- Add an `is_blocked` column to the `urls` table; return HTTP 403 for blocked URLs.

**Non-Goals:**
- Analytics event publishing (deferred to a message-queue change).
- URL expiration / TTL (requires a `expires_at` column and a cleanup worker — deferred).
- `is_deleted` / soft-delete (deferred).
- Rate limiting on the redirect endpoint (deferred).
- Custom 404/403 HTML pages (plain JSON body for now).

## Decisions

### Resolve flow

```
GET /{short_code}
  │
  ├─ validate Base62 chars (regex ^[0-9A-Za-z]+$)
  │
  ├─ use_case: ResolveURL.execute(code)
  │     │
  │     ├─ decode Base62 → snowflake_id
  │     │
  │     ├─ try cache.get(snowflake_id)
  │     │    ├─ HIT (positive) → return URL, status=ok
  │     │    ├─ HIT (negative sentinel) → return status=not_found
  │     │    └─ MISS or ConnectionError → fall through to DB
  │     │
  │     ├─ db_repository.find_by_id(snowflake_id)
  │     │    ├─ found, not blocked → cache.set + return URL, status=ok
  │     │    ├─ found, blocked     → return status=blocked
  │     │    └─ not found          → cache.set(negative_sentinel) + return status=not_found
  │     │
  │     └─ return (status, url?)
  │
  └─ route → 302 + Location / 404 / 403
```

### Cache value encoding

Redis stores a string value per key. We use JSON to encode the record state:

```json
{"s": "ok", "u": "https://..."}
{"s": "null"}   // negative sentinel — ID does not exist
```

The `s` field signals the route what HTTP status to return. This avoids a second DB round-trip on cache hit for non-existent or blocked IDs.

### Cache TTLs

| Scenario | TTL | Rationale |
|----------|-----|-----------|
| Positive hit (valid URL) | 3600 s | URLs change rarely; 1h is a good balance |
| Negative sentinel | 30 s | Short enough to accept a new `POST /Create-URL` for the same ID, long enough to absorb bursts |
| Blocked sentinel | 300 s | Block decisions change on admin timescale, not per-second |

### Redis client

`redis.asyncio.Redis` (from `redis-py`). Single connection pool created at startup and injected via dependencies — same pattern as the engine/session.

### Graceful degradation

The cache adapter wraps every `get`/`set` in a `try/except redis.ConnectionError`. On connection failure it logs a warning and returns `MISS`, causing the use case to fall through to the DB. The service stays up (degraded).

### is_blocked column

Add `is_blocked: Boolean` to the `Url` model (default `False`). The Alembic migration is auto-generated with `--autogenerate`. Spec requirement `Requirement: Fail closed on persistence errors` in the existing spec is not affected — this is a new read path concern, not a change to the existing write path.

### Negative caching via sentinel

When `find_by_id` returns `None`, the use case instructs the cache adapter to store a sentinel JSON `{"s": "null"}` with a 30-second TTL. Subsequent requests for the same ID hit the cache fast path and return 404 without touching PostgreSQL.

### DB repository addition

Add `UrlRepository.find_by_id(id: int) -> UrlRecord | None` as a new method on the existing `SqlAlchemyUrlRepository`. This gives us a DB read for the existing `urls` table — no new table.

## Risks / Trade-offs

- **[Redis connection pool exhaustion]** App-level pool sizing. Start with `max_connections=10` and monitor.
- **[Sentinel key explosion on 404 flood]** Each non-existent ID creates a key. Mitigation: 30-second TTL auto-evicts stale keys; Redis memory is cheap for this pattern.
- **[Stale positive cache]** A blocked URL could be cached as "ok" for up to 1 hour. Mitigation: the admin action to block a URL should also invalidate the cache key. Not implemented in this change — documented as a follow-up.
- **[Model migration]** Adding `is_blocked` requires a new Alembic revision. Rollback: `alembic downgrade -1`.
- **[No auth on redirect endpoint]** Any client can resolve any short code. Acceptable for MVP; authentication deferred.

## Migration Plan

1. Run `alembic revision --autogenerate -m "add is_blocked to urls"` against MySQL.
2. Apply: `alembic upgrade head`.
3. Rollback: `alembic downgrade -1`.

## Open Questions

- **`is_blocked` column name** — using `is_blocked` boolean with default `False`. Confirm naming convention.
- **Analytics integration point** — the use case will emit an event (log line or call a publisher port). The actual broker (RabbitMQ / Redis Streams / Kafka) is deferred. For now we just log the redirect event.
