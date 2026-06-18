## Context

Shorty uses proxy-based authentication via `X-Authenticated-User` header (HMAC-signed when `PROXY_SHARED_SECRET` is set). There is currently no role concept — every authenticated user is treated equally. The `urls` table already has an `is_blocked` boolean column (default `false`) with no API to modify it.

The admin panel introduces a lightweight role system: a static list of admin emails configured via environment variable.

## Goals / Non-Goals

**Goals:**
- Identify admins via `ADMIN_EMAILS` environment variable (comma-separated email list)
- `POST /admin/block/{short_code}` — set `is_blocked = true`
- `POST /admin/unblock/{short_code}` — set `is_blocked = false`
- `GET /admin/urls` — paginated list of all URLs (any owner) with `created_by` field
- Admin auth fails with 403 before rate limiting or business logic

**Non-Goals:**
- Database roles table (overkill for static admin list)
- Granular permissions (block-only vs full-admin)
- Admin audit log of who blocked what
- Admin dashboard UI

## Decisions

### Admin identification: `ADMIN_EMAILS` env var

```bash
ADMIN_EMAILS=admin@empresa.com,jefe@empresa.com
```

Parsed at startup into a `frozenset[str]`. The `require_admin_user` dependency checks membership with O(1) lookup.

Alternative considered: Entra ID groups via a second header. Rejected because it depends on proxy configuration outside our control. The static list works immediately and can be migrated to group-based later without API changes.

### Admin auth dependency: wraps `require_authenticated_user`

```python
async def require_admin_user(
    authenticated_user: AuthenticatedUserDep,
    settings: SettingsDep,
) -> str:
    if authenticated_user not in settings.admin_emails:
        raise HTTPException(403)
    return authenticated_user
```

Order in routes: `AuthenticatedUserDep` → `require_admin_user` → `RateLimitDep` → use case.

### Block/Unblock: atomic boolean toggle

Single repository method `update_blocked(id, blocked)` avoids two separate methods. The use cases just call it with `True` or `False`. Returns count of affected rows for existence checking.

### Admin URL listing: reuse `find_all_by_created_by` pattern

New `find_all(cursor, limit)` method on `UrlRepository` returns all URLs ordered by `id DESC` with cursor pagination. Reuses the same `ListMyUrls` result structure but without `created_by` filter. The admin list response includes `created_by` so admins can see who owns each URL.

### Route prefix: `/admin`

Separate FastAPI router with prefix `/admin`. Registered before `redirect` router and after `my_urls` router. No route conflicts: `/admin` is not a valid Base62 string so it can't match the redirect handler even if registered earlier.

### Cache invalidation on block/unblock

Blocking a URL that's cached as "ok" must invalidate the cache so the next redirect returns 403 instead. Unblocking must similarly evict the "blocked" sentinel. The use cases delete the Redis key for the URL's Snowflake ID.

## Risks / Trade-offs

- [Static admin list] Adding/removing admins requires env var change + app restart. Acceptable for small orgs; can migrate to dynamic roles later.
- [No block audit trail] No record of who blocked what or when. Acceptable for v1; can add later.
- [Blocked URLs still visible] Users can still see their blocked URLs in `/my-urls` and detail views. This is intentional transparency — they should know their URL was blocked.
