## Why

Authenticated users can create short URLs via `POST /Create-URL` and the resulting rows are already tagged with `created_by` (the user's email) and indexed, but there is **no way for a user to manage URLs they have already created**. The most acute gap is deletion: once a user creates a short link, it persists for 60 days (or until the hourly cleanup purges it), and there is no way for the user to revoke it earlier. This is a basic hygiene feature for a URL shortener — typos, sensitive content leaks, accidental shares, and link rot all demand a self-service kill switch.

This change introduces that kill switch. It is scoped narrowly to **soft delete** (no listing, no detail view, no editing — those are out of scope for this change and will be follow-ups).

## What Changes

- Add a new endpoint `DELETE /my-urls/{short_code}` that lets an authenticated user soft-delete their own URL.
- Add a `deleted_at` column to the `urls` table, indexed for the cleanup worker.
- Modify `GET /{short_code}` so that a soft-deleted URL responds with `410 Gone` (same as expired) rather than `302` or `404`.
- Modify the hourly cleanup worker to also hard-delete rows where `deleted_at <= now() - 30 days`.
- Add a `soft_delete(id)` method to the repository and a `SoftDeleteMyUrl` use case.
- Add `delete` to the cache port (or reuse an existing invalidation path) so the Redis entry is evicted immediately on delete.

The endpoint, repository, and use case are reuse-friendly so that the follow-up `GET /my-urls` (list) and `GET /my-urls/{short_code}` (detail) changes can plug into the same authorization pattern.

## Capabilities

### New Capabilities

- `user-url-soft-delete`: Allows an authenticated user to soft-delete a URL they previously created, with idempotent semantics, race-safe behavior, and a deferred hard-delete window managed by the existing cleanup worker.

### Modified Capabilities

- `url-redirect`: Adds a new state to the redirect resolution pipeline: a URL whose `deleted_at IS NOT NULL` MUST be treated as gone and return `410 Gone`, regardless of `expires_at` or `is_blocked`. Order of evaluation in the redirect use case becomes: invalid code → `400`, blocked → `403`, deleted → `410`, expired → `410`, missing → `404`, OK → `302`.
- `url-expiration`: The hourly cleanup worker SHALL also delete rows whose `deleted_at <= now() - 30 days`, in addition to the existing `expires_at <= now()` deletion. The two queries are independent and both run on each cycle.

## Impact

- **DB schema**: new column `urls.deleted_at TIMESTAMP WITH TIME ZONE NULL` + new index `ix_urls_deleted_at`. New Alembic migration required.
- **Domain model**: `UrlRecord` gains a `deleted_at: datetime | None` field.
- **Repository**: new method `soft_delete(id: int) -> None`.
- **Cache port**: needs a `delete(key: str)` method (or reuse whichever invalidation primitive already exists for cache writes).
- **Use cases**: new `SoftDeleteMyUrl` use case in `src/core/usecases/`.
- **API routes**: new `DELETE /my-urls/{short_code}` in a new `src/api/routes/my_urls.py` (or appended to an existing routes file).
- **API dependencies**: reuse `require_authenticated_user`. New rate-limiter bucket for `/my-urls` (separate from create/redirect buckets).
- **Redirect path**: `ResolveURL` use case must inspect `deleted_at` and emit a `DELETED` status (or fold the check into the existing `EXPIRED` branch — design decision recorded in `design.md`).
- **Cleanup loop**: `src/api/main.py` lifespan adds a second DELETE query inside the existing hourly cycle.
- **Tests**: new unit tests for the use case and repository, new integration tests for the endpoint and for the redirect behavior on deleted URLs, new tests for the cleanup query.

Out of scope (deferred): `GET /my-urls` listing, `GET /my-urls/{short_code}` detail, restore-from-trash, edit, bulk operations, custom short codes, configurable TTL at creation time, click counts, tags, search, users table, admin endpoints.
