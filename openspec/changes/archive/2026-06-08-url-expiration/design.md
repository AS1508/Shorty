## Context

Shorty currently supports creating short URLs via `POST /Create-URL` with Snowflake ID generation, Base62 encoding, HMAC-authenticated requests, and PostgreSQL persistence. There is no redirection endpoint and no expiration mechanism — once created, links live forever.

This design adds a dual-validation expiration strategy: lazy validation on every read plus periodic background cleanup. All timestamps use UTC exclusively.

## Goals / Non-Goals

**Goals:**
- Every new short URL gets `expires_at = created_at + 60 days` (UTC) automatically.
- A `GET /<code>` endpoint resolves short codes, checks expiration, and redirects (302) or returns 410 Gone.
- Cache layer uses Redis native TTL for automatic key eviction at 60 days.
- Background worker purges expired rows from MySQL periodically.
- Shortcode generation reuses expired-but-not-yet-purged codes (soft collision resolution).

**Non-Goals:**
- User-configurable TTL (strictly 60 days for all links).
- Email/webhook notifications on link expiration.
- UI for managing or previewing expiration status.
- Archival or soft-delete of expired records (hard delete only).
- Per-link TTL reporting in API responses (can be added later).

## Decisions

### Decision 1: Expiration constant — 60 days

**Choice**: Hardcoded `URL_TTL_SECONDS = 5_184_000` (60 × 24 × 3600) as a module-level constant.

**Alternatives**: Environment variable or per-request parameter. Rejected because current scope mandates a fixed default with no user override.

### Decision 2: Lazy expiration + active purge (dual validation)

**Choice**: At read time, the system compares `expires_at < now(UTC)` before redirecting (lazy). Separately, a background asyncio loop deletes expired rows from PostgreSQL every N minutes (active purge).

**Rationale**: The lazy check is the primary enforcement mechanism and works even if the worker is down. The active purge keeps storage bounded and prevents unbounded table growth. Redis TTL provides a third layer of defense at the cache level.

### Decision 3: HTTP 410 Gone for expired URLs

**Choice**: Return `410 Gone` when a short code exists but `expires_at < now(UTC)`. Return `404 Not Found` only when the short code has no matching row at all.

**Rationale**: 410 communicates permanent removal (the resource existed but is gone), which is semantically more accurate than 404 for expired links. This allows clients and crawlers to distinguish "never existed" from "expired."

### Decision 4: 302 Found for active redirects

**Choice**: Use `302 Found` (temporary redirect) rather than `301 Moved Permanently`.

**Rationale**: 301 is cacheable by browsers indefinitely, which would cause clients to bypass the resolver entirely on subsequent visits — meaning they'd never hit the expiration check again. 302 ensures every request reaches the server for validation.

### Decision 5: Redis EXPIRE per key

**Choice**: Call `EXPIRE <key> <60_days_seconds>` after every `SET` on the short code key.

**Rationale**: Uses Redis built-in TTL rather than application-level timestamp comparison in cache, reducing memory overhead for expired keys and avoiding stale cache reads.

### Decision 6: Background cleanup via asyncio task

**Choice**: An `asyncio.create_task` loop in the FastAPI lifespan, sleeping `CLEANUP_INTERVAL_SECONDS` (default 3600) between purge cycles. No external scheduler (no Celery, no APScheduler).

**Rationale**: Minimizes dependencies. The worker runs in-process and shares the database connection pool. For a single-process deployment, this is sufficient. A cron-based approach would require a separate process and is better suited for multi-replica deployments, which can be added later.

### Decision 7: Soft collision resolution for expired shortcodes

**Choice**: When generating a new short code, if the generated code already exists in the database but its `expires_at < now(UTC)`, treat it as available and overwrite (or delete first, then insert).

**Rationale**: Avoids wasting short code space on expired but not-yet-purged records. The background worker eventually cleans up, but this handles the race condition proactively.

## Risks / Trade-offs

- **Worker crash leaves expired rows in DB**: Mitigated — lazy validation at read time still rejects expired URLs. The worker is a best-effort cleanup, not the enforcement mechanism.
- **Clock skew between app server and DB**: Mitigated — both read UTC from the same source (database function `NOW()` or Python `datetime.now(UTC)`). App-layer validation uses Python UTC; DB-layer uses `NOW()`.
- **High traffic on a single short code with near-expiry**: No special handling needed; each request independently checks `expires_at`. Cache hit avoids DB query entirely until Redis TTL expires.
- **Leap seconds**: Python's `timedelta(days=60)` is based on 86400-second days and does not account for leap seconds. The 60-day window may be off by up to ~1 second. Acceptable given the use case.
- **Short code collision with freshly-expired key in Redis**: Redis TTL is set to exactly 60 days. If the worker hasn't purged the DB row yet and a new URL happens to generate the same code, the old Redis key may still exist. Mitigated — the new `SET` overwrites the old key and resets TTL.
