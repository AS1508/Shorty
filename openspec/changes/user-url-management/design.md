## Context

Shorty uses clean architecture (ports & adapters). The core layer defines `UrlRepository` as a `Protocol` with methods for insert, find_by_id, soft_delete, and deletion queries. The API layer uses FastAPI dependency injection to wire use cases with `AppState` singletons (Snowflake generator, Redis cache, session factory).

Currently `DELETE /my-urls/{short_code}` exists at `src/api/routes/my_urls.py` with prefix `/my-urls`. Auth uses `X-Authenticated-User` (HMAC-signed), rate limiting via `MyUrlsRateLimitDep` (60 req/60s default).

The `urls` table has an index on `created_by` and URLs are identified by Snowflake ID (monotonically increasing).

## Goals / Non-Goals

**Goals:**
- Provide `GET /my-urls` with cursor-based pagination (default 20, max 100 items per page, ordered by id DESC / newest first)
- Provide `GET /my-urls/{short_code}` with ownership verification and full metadata
- Add `find_all_by_created_by(created_by, cursor, limit)` to `UrlRepository`
- Reuse existing auth (`AuthenticatedUserDep`) and rate limiting (`MyUrlsRateLimitDep`) machinery
- Expose `is_expired`, `is_blocked`, `deleted_at` in both list and detail responses so the user has full visibility

**Non-Goals:**
- Filtering by status (active/expired/deleted)
- Search by original URL
- Sorting options beyond newest-first
- Analytics or click stats
- Admin endpoint for cross-user listing
- Caching list responses in Redis (per-user queries don't benefit from shared cache)

## Decisions

### Pagination: Cursor-based via Snowflake ID
Snowflake IDs are monotonically increasing, so ordering by `id DESC` yields newest-first without expensive OFFSET. Cursor = last item's `id` from current page. Query: `WHERE created_by = :email AND id < :cursor ORDER BY id DESC LIMIT :limit`. No cursor → start from newest. This avoids OFFSET drift and performs well at any page depth.

### Short URL construction in route layer
`short_url` = `settings.short_base_url + "/" + short_code`. The use case returns domain objects (`UrlRecord`), the route builds the response DTO. This keeps presentation logic out of core.

### `is_expired` computed at query time
The `is_expired` field is computed by comparing `expires_at` with `datetime.now(UTC)`. The existing `is_expired()` function from `src/core/expiration.py` is reused. The list use case computes this per record.

### Composite index not needed yet
The `ORDER BY id DESC` with `WHERE created_by = :email` can use the existing `ix_urls_created_by` index (MySQL InnoDB secondary index includes the PK). A composite `(created_by, id)` index would be more efficient for large datasets, but can be added later as a migration if needed.

### 404 for ownership mismatch (not 403)
Returns `404` when the URL belongs to another user, matching the existing pattern in `DELETE /my-urls/{short_code}`. This avoids revealing whether a short code exists at all.

## Risks / Trade-offs

- [Cursor stability] Deleting a URL that is the last item of a page shifts the cursor target. The next page query uses `id < cursor_idx` so it naturally skips deleted items. Trade-off: a URL created between two page fetches might be missed if its ID happens to be > cursor. This is acceptable — pagination provides a snapshot, not real-time consistency.
- [Performance at scale] `find_all_by_created_by` does a full table scan if `created_by` has many URLs and MySQL chooses a different plan. Mitigation: the `ix_urls_created_by` index covers the WHERE clause. If profiling shows issues, add a composite index `(created_by, id DESC)`.
- [Blocked URL visibility] Users can see `is_blocked: true` but cannot unblock — that's an admin action outside this change. This is intentional transparency.
