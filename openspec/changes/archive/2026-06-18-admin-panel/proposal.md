## Why

The `is_blocked` column exists in the database but has no API to set or unset it. Without admin endpoints, there is no way to block malicious URLs or audit all short links across the organization. A human or automated process needs the ability to moderate content.

## What Changes

- **`ADMIN_EMAILS` env var**: Comma-separated list of admin emails. Users matching this list get admin privileges.
- **Admin auth dependency**: New `require_admin_user` FastAPI dependency that checks the authenticated user against the admin list. Returns 403 for non-admins.
- **`POST /admin/block/{short_code}`**: Sets `is_blocked = true` on the URL. Blocked URLs return 403 on redirect.
- **`POST /admin/unblock/{short_code}`**: Sets `is_blocked = false`. Restores normal redirect behavior.
- **`GET /admin/urls`**: Paginated list of ALL URLs (any user). Supports same cursor-based pagination as `/my-urls`. Includes `created_by` in the response so admins can identify the owner.

No breaking changes. No schema migrations required (`is_blocked` already exists).

## Capabilities

### New Capabilities

- `admin-panel`: Administrators (identified via `ADMIN_EMAILS` environment variable) can block/unblock any short URL and list all URLs across all users.

### Modified Capabilities

*(None.)*

## Impact

- **New files**: `src/api/routes/admin.py`, `src/core/usecases/block_url.py`, `src/core/usecases/unblock_url.py`, `src/core/usecases/list_all_urls.py`
- **Modified files**: `src/infra/config.py` (add `admin_emails`), `src/api/dependencies.py` (add `require_admin_user`), `src/api/main.py` (register admin router), `src/core/ports.py` (add `find_all`), `src/infra/db/repository.py` (add `update_blocked`, `find_all`)
- **API surface**: Three new endpoints under `/admin`
- **Dependencies**: None
- **Tests**: Unit tests for use cases, integration tests for admin endpoints
