## Why

Users can create and delete their own short URLs, but have no way to see what they've created. The only "management" action available is delete. This forces users to track their short codes externally and makes it impossible to audit, monitor expiration, or revisit URLs they've shortened.

## What Changes

- **`GET /my-urls`**: New paginated list endpoint returning all URLs owned by the authenticated user (newest first).
- **`GET /my-urls/{short_code}`**: New detail endpoint returning metadata for a single URL owned by the authenticated user.
- **`ListMyUrls`** use case with cursor-based pagination via Snowflake ID.
- **`GetMyUrl`** use case with ownership verification.
- **`find_all_by_created_by`** method on `UrlRepository`.
- Response DTOs including `short_code`, `short_url`, `original_url`, `created_at`, `expires_at`, `is_expired`, `is_blocked`, and `deleted_at`.

No breaking changes. No schema migrations required.

## Capabilities

### New Capabilities

- `user-url-management`: Authenticated users can list their own short URLs with cursor-based pagination and view metadata for individual URLs.

### Modified Capabilities

*(None — existing specs are unchanged.)*

## Impact

- **New files**: `src/core/usecases/list_my_urls.py`, `src/core/usecases/get_my_url.py`
- **Modified files**: `src/core/ports.py` (add `find_all_by_created_by`), `src/infra/db/repository.py` (implement method), `src/api/dependencies.py` (wire new use cases), `src/api/main.py` (no change — existing my_urls router handles both), `src/api/routes/my_urls.py` (add handlers)
- **API surface**: Two new GET endpoints under `/my-urls`
- **Dependencies**: None
- **Tests**: New unit tests for both use cases, new integration tests for both endpoints
