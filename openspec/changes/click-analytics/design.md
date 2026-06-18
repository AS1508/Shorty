## Context

Shorty currently has no click tracking. The `GET /{short_code}` redirect endpoint resolves the URL and returns a 302 without recording the event. The `urls` table has no counter column. Users have no way to know if their links are being used.

## Goals / Non-Goals

**Goals:**
- Add `clicks BIGINT NOT NULL DEFAULT 0` to the `urls` table via Alembic migration
- Increment `clicks` atomically on every successful redirect (status 302 only — not on 403/404/410)
- Expose `clicks` in `/my-urls` list and `/my-urls/{short_code}` detail responses
- Expose `clicks` in admin `/admin/urls` list responses
- Provide `GET /admin/stats/{short_code}` for admin access to any URL's click count

**Non-Goals:**
- Time-series analytics (clicks per day/hour)
- Geographic or referrer tracking
- Real-time streaming of click events
- Click fraud detection
- Admin dashboard aggregating total clicks across all URLs

## Decisions

### Atomic increment in repository
`increment_clicks(id)` runs `UPDATE urls SET clicks = clicks + 1 WHERE id = :id`. Atomic at the database level — no race conditions under concurrent redirects. The increment happens only for successful resolutions (302), not for blocked/expired/deleted/not-found responses.

### Increment in the resolve use case
The `ResolveURL` use case already distinguishes statuses. After confirming `ResolveStatus.OK` and before returning the result, it calls `repository.increment_clicks(snowflake_id)`. This keeps the increment logic in the core layer.

### Silent failure on increment errors
If the increment query fails (e.g., temporary DB issue), the redirect still proceeds. A warning is logged. Rationale: a click counter should never block a user's redirect.

### `clicks` in response DTOs
The field is computed from `UrlRecord.clicks` and added to existing response builders in the route layer. No new use cases needed for reading clicks — it's part of the record.

### `GET /admin/stats/{short_code}` for admin
Admin can view click count for any URL (own or someone else's). Uses existing `GetMyUrl`-style lookup but without ownership check. Returns the full record including clicks.

### Migration: single column addition
```sql
ALTER TABLE urls ADD COLUMN clicks BIGINT NOT NULL DEFAULT 0;
```
No data migration needed — existing URLs start at 0 clicks. The column is not indexed (no query filtering by clicks).

## Risks / Trade-offs

- [DB write on every redirect] Every 302 now incurs an UPDATE. This increases DB load on read-heavy traffic. Mitigation: the increment is a simple atomic counter update — minimal overhead. If profiling shows issues, batch updates via Redis can be added later.
- [Counter reset on delete/expiry] If a URL is purged by the cleanup worker, its click count is lost. Acceptable — the URL no longer exists, so analytics are irrelevant.
- [`clicks` field in existing responses] Adding `clicks` to `/my-urls` responses is backward-compatible (additive field). No client should break.
