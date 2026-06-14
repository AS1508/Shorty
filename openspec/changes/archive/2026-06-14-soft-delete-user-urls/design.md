## Context

The system already persists `created_by` (a nullable email string) on every URL row created through `POST /Create-URL`, and the column has an index (`ix_urls_created_by`). Authentication is handled by a proxy that injects `X-Authenticated-User` and an HMAC signature, validated by `require_authenticated_user` in `src/api/dependencies.py`. The only authenticated endpoint today is `POST /Create-URL`; everything else is unauthenticated (`GET /{short_code}` is public).

There is no soft-delete mechanism. Once a URL is created, the only way it leaves the system is the 60-day expiration enforced by the hourly cleanup worker. Users have no self-service way to revoke a URL.

The two existing route modules are `src/api/routes/shortener.py` and `src/api/routes/redirect.py`. The `ResolveURL` use case already produces a small enum of statuses (`OK`, `NOT_FOUND`, `BLOCKED`, `EXPIRED`) that the redirect route maps to HTTP status codes. The cache port (`CachePort`) exposes `get`, `set`, `incr`, `expire`, and `aclose` — there is no `delete` primitive today.

The change introduces a self-service soft-delete flow that integrates with the existing redirect pipeline and cleanup worker without disturbing their existing behavior.

## Goals / Non-Goals

**Goals:**

- Expose `DELETE /my-urls/{short_code}` for authenticated users.
- Make the soft-delete operation idempotent and race-safe.
- Make soft-deleted URLs unreachable through `GET /{short_code}` (returning `410 Gone`).
- Reuse the existing auth dependency and rate-limiting infrastructure (with a new bucket for `/my-urls/*`).
- Have the existing hourly cleanup worker hard-delete soft-deleted rows after a 30-day grace period.
- Stay within the existing port/hexagonal layering (no leakage of SQLAlchemy types into the use case or routes).

**Non-Goals:**

- `GET /my-urls` (list) and `GET /my-urls/{short_code}` (detail). These are deferred; the new route file, dependency wiring, and use case shape are designed so that adding them later is a localized change.
- A "trash" or "restore" endpoint. Soft-deleted URLs are not user-restorable.
- A `users` table. The existing `created_by: VARCHAR(254)` is the only identity surface; this change does not introduce a `User` entity, FK, or role system.
- Custom short codes, configurable TTL, click counters, tags, search, filtering, bulk operations, admin endpoints. All deferred.
- A new rate-limiting algorithm. We add a new **bucket key** (`rate:my_urls:{email}`) but reuse the `FixedWindowRateLimiter` implementation.
- A new cache backend. We extend the existing `CachePort` with a `delete` method; the in-memory fake and the Redis adapter both implement it.

## Decisions

### D1 — Authorization check lives in the use case, not the route

The route extracts the authenticated email via `require_authenticated_user` and passes it to the `SoftDeleteMyUrl` use case. The use case looks up the URL by id and then verifies `record.created_by == current_email`. The repository is not given the email — it stays a generic "URL by id" lookup.

**Why**: keeps the route dumb and the authorization policy testable at the use-case level. Also makes the 404-for-others behavior trivial: if `created_by` does not match, the use case returns "not found" without leaking existence. A repository method that filters by `created_by` would work too, but it makes the race-safety reasoning slightly trickier and it duplicates an index on the same column we already filter on in the use case.

### D2 — Idempotency via `WHERE deleted_at IS NULL` on the UPDATE

The repository's `soft_delete(id)` issues:

```sql
UPDATE urls SET deleted_at = :now WHERE id = :id AND deleted_at IS NULL
```

The use case first does `find_by_id(id)`. If the record does not exist, it returns 404. If `created_by` does not match, it returns 404. If `deleted_at` is already set, it returns 404 (idempotent). Otherwise it issues the UPDATE and inspects the rowcount: 1 → 204, 0 → 404 (concurrent deletion race).

**Why**: this is naturally idempotent and race-safe without explicit locking. Two concurrent DELETEs both pass the existence/ownership/deletion check, then race on the UPDATE; the second UPDATE matches zero rows because `deleted_at IS NULL` is no longer true. The second client receives 404, which matches the spec.

### D3 — Add a `DELETED` status to the resolve pipeline, do not fold into `EXPIRED`

Extend `ResolveStatus` with `DELETED`. The redirect route maps `DELETED → 410 Gone` with the same body shape as `EXPIRED`. Sentinel value in Redis: a distinct marker (e.g., `"__deleted__"`) with a 300-second TTL, mirroring how `BLOCKED` and `EXPIRED` already have their own sentinels.

**Why**: a soft-deleted URL is conceptually distinct from an expired one — it could still be inside its 60-day window. Conflating them obscures both future analytics and any future "undelete" path (out of scope, but the data stays clean). Using the same HTTP status (410) keeps the public API consistent: the user only sees a "this link is gone" message regardless of which mechanism produced it.

### D4 — Add `delete(key)` to `CachePort`, not a sentinel-set workaround

Extend the `CachePort` protocol with:

```python
def delete(self, key: str) -> None: ...
```

The Redis adapter issues a `DEL`; the in-memory test fake pops the key. Fail-open semantics: if the cache raises, the soft-delete still succeeds. The DB is the source of truth; cache invalidation is best-effort, and stale cache entries will be replaced on the next read attempt anyway (the cache miss will fetch the now-deleted record and the resolve pipeline will set a `DELETED` sentinel).

**Why**: `set` with a sentinel would also work, but it leaves a stale-but-correct entry that has to be re-read before a new "OK" status can be written. `DEL` is the natural primitive. The fail-open behavior mirrors the rest of the cache layer.

### D5 — Hard-delete window: 30 days, as a module-level constant

```python
# src/core/expiration.py (or a sibling)
SOFT_DELETE_PURGE_DAYS = 30
```

The cleanup worker adds a second query:

```sql
DELETE FROM urls WHERE deleted_at IS NOT NULL AND deleted_at <= now() - interval '30 days'
```

The existing `expires_at` query is unchanged and continues to run on the same hourly cycle.

**Why**: 30 days gives users a generous restore window if a follow-up "trash" feature is added, while bounding the storage cost of soft-deleted rows. Hard-coded for now; promoting to a config value is a one-line change when needed.

### D6 — New route file: `src/api/routes/my_urls.py`

The new `DELETE /my-urls/{short_code}` lives in a new routes module rather than being appended to `shortener.py`. The reasoning is twofold: (a) `shortener.py` is named for the creation path and adding a delete endpoint there would dilute that, (b) the next two endpoints from SPEC-02 and SPEC-03 are also under `/my-urls` and benefit from their own file. The new file registers the router in `src/api/main.py` alongside the other two.

**Why**: matches the way the existing code groups routes by feature, keeps each file small, and makes the follow-up list/detail endpoints a one-file expansion.

### D7 — New rate-limit bucket: `rate:my_urls:{email}:{window_ts}`

Add a new `rate_limit_my_urls_count` and `rate_limit_my_urls_window_seconds` setting pair (defaults: 60 req / 60 s per email). Add a new `MyUrlsRateLimitDep` dependency that wraps the existing `FixedWindowRateLimiter` with a `bucket="my_urls"` argument.

**Why**: SPEC-01 CA-12 mandates an independent bucket. Reusing the create bucket would couple write-once creation with a potentially noisier management path and make their cost attribution impossible.

### D8 — URL validation reuses the redirect's regex

The short code format check is already implemented inside the redirect route. The new route imports the same constant (`BASE62_PATTERN` or whatever the project calls it) and rejects with 400 before touching the use case. We do not duplicate the regex.

## Risks / Trade-offs

- **R1: Soft delete means the `urls` table grows transiently.** A user who deletes a URL keeps its row in the DB for 30 days. → Mitigation: 30-day hard-delete is enforced by the same hourly worker that already exists. The growth is bounded by `(deletions per day) × 30` rows.
- **R2: `created_by` is a denormalized email string, not a FK.** If the org's email scheme changes (e.g., a user is renamed), the link to their URLs is lost. → Accepted for this change: same trade-off the project already accepted for `created_by`. Mitigation is a future `users` table change, not in scope here.
- **R3: A new public status (`DELETED`) leaks information that a deleted URL once existed.** For `GET /{short_code}`, the difference between 410 (deleted) and 404 (never existed) is observable. → Accepted: this matches the existing behavior for expired URLs (also 410) and is required by SPEC-01 R4.3. The 410 body is generic ("this short link is gone"), so a third party cannot distinguish a soft-deleted from an expired URL without a side channel.
- **R4: The new route adds a third authenticated endpoint, increasing the surface for HMAC-related bugs.** → Mitigation: the route reuses `require_authenticated_user` verbatim. The auth code is not modified. The integration tests explicitly cover missing-header and invalid-signature cases.
- **R5: The `CachePort.delete` change is a protocol-level addition that could break custom implementations.** → Mitigation: the only known implementations are the Redis adapter and the in-memory test fake, both updated in the same change. If a third implementation exists outside the repo, it will fail to type-check (`mypy --strict`) and the maintainer will see the protocol violation.
- **R6: The DELETE request mutates state but has no body. If a client sends a body, FastAPI will accept and ignore it.** → Accepted: standard HTTP behavior. No 415/400 logic needed.
- **R7: The 30-day window is hard-coded.** A change in policy requires a code change. → Accepted for MVP; this is a one-line move to a config setting when a follow-up requires it.

## Migration Plan

- **New Alembic migration**: `alembic/versions/<rev>_add_deleted_at_to_urls.py` that does:
  - `ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE NULL` to `urls`.
  - `CREATE INDEX ix_urls_deleted_at ON urls (deleted_at)`.
  - Downgrade: `DROP INDEX ix_urls_deleted_at`, `DROP COLUMN deleted_at`.
- **No data backfill**: existing rows have `deleted_at = NULL`, which is the correct "not deleted" state. The migration is non-destructive and instantaneous on an empty table; on a populated table, adding a nullable column without a default is fast in MySQL 8 (instant ADD COLUMN with `INSTANT` algorithm for nullable columns).
- **Deploy order**:
  1. Run `alembic upgrade head` (adds column + index, no app code impact).
  2. Deploy new application code. Old code reading `urls` is unaffected by the extra column.
  3. Restart. Workers pick up the new code, including the new cleanup query and the new route.
- **Rollback**:
  1. Roll back the application to the previous version. The new route stops responding (404), the redirect path stops returning 410 for deleted URLs (back to 302/404 based on `expires_at`), and the cleanup query stops running.
  2. Optionally run `alembic downgrade -1` to drop the column. Rows created between the upgrade and the rollback keep their `deleted_at` values, but the column is dropped along with them — **soft-deleted URLs will reappear as active if a downgrade is performed before the worker runs hard-delete**. Mitigation: do not downgrade in production unless necessary; if you must, run the worker manually first.
- **Forward-compatibility**: the migration is additive (nullable column). It does not block any concurrent readers. The application is forward-compatible with a missing `deleted_at` column only if explicitly versioned — outside the scope of this design.

## Open Questions

- OQ1: Should the `deleted_at` be set to `now()` from the application (Python clock) or `CURRENT_TIMESTAMP` from MySQL? → **Resolution in tasks.md**: use MySQL `CURRENT_TIMESTAMP` (via `server_default` on a column) is not possible here because we need the value at UPDATE time, not at INSERT time. The UPDATE will pass `now()` as a parameter from the application, which is acceptable for a single-instance deploy; for multi-region consistency, a future change could switch to `CURRENT_TIMESTAMP` at the database level.
- OQ2: Does the cleanup worker's second query need to be in a separate transaction from the first? → **Resolution**: yes — two `DELETE`s, two implicit transactions. If one fails, the other should still run. Each is wrapped in `async with session.begin()` independently.
- OQ3: Should the new endpoint require `Content-Length: 0`? → **Resolution**: no. FastAPI ignores bodies on DELETE; the request handler will not look at a body. Adding the check is over-engineering.
