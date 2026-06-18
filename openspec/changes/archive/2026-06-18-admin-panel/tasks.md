## 1. Config — Admin identification

- [x] 1.1 Add `admin_emails: frozenset[str]` field to `Settings` in `src/infra/config.py`, parsing `ADMIN_EMAILS` env var (comma-separated, empty string = empty set)

## 2. Auth — Admin dependency

- [x] 2.1 Add `require_admin_user` dependency in `src/api/dependencies.py` that wraps `AuthenticatedUserDep` and checks membership in `settings.admin_emails`
- [x] 2.2 Add `AdminUserDep` type alias

## 3. Repository — Block/unblock + find all

- [x] 3.1 Add `update_blocked(id, blocked)` and `find_all(cursor, limit)` to `UrlRepository` protocol in `src/core/ports.py`
- [x] 3.2 Implement `update_blocked` in `SqlAlchemyUrlRepository` (atomic UPDATE)
- [x] 3.3 Implement `find_all` in `SqlAlchemyUrlRepository` (cursor-based, ordered by id DESC)

## 4. Use Cases

- [x] 4.1 Create `BlockUrl` use case in `src/core/usecases/block_url.py` (decode, update blocked=true, evict cache)
- [x] 4.2 Create `UnblockUrl` use case in `src/core/usecases/unblock_url.py` (decode, update blocked=false, evict cache)
- [x] 4.3 Create `ListAllUrls` use case in `src/core/usecases/list_all_urls.py` (no ownership filter, includes created_by)

## 5. API — Dependencies & Wiring

- [x] 5.1 Add `get_block_url`, `get_unblock_url`, `get_list_all_urls` factory functions in `src/api/dependencies.py`
- [x] 5.2 Add `BlockUrlDep`, `UnblockUrlDep`, `ListAllUrlsDep` type aliases

## 6. API — Admin routes

- [x] 6.1 Create `src/api/routes/admin.py` with router prefix `/admin`
- [x] 6.2 Add `POST /admin/block/{short_code}` handler
- [x] 6.3 Add `POST /admin/unblock/{short_code}` handler
- [x] 6.4 Add `GET /admin/urls` handler with pagination and `created_by` in response
- [x] 6.5 Register admin router in `src/api/main.py` (after my_urls, before redirect)

## 7. Tests — Unit

- [x] 7.1 Write `tests/unit/test_block_url.py`
- [x] 7.2 Write `tests/unit/test_unblock_url.py`
- [x] 7.3 Write `tests/unit/test_list_all_urls.py`

## 8. Tests — Integration

- [x] 8.1 Write `tests/integration/test_admin_endpoints.py` covering block, unblock, list, auth rejection, non-admin rejection, cache invalidation

## 9. Verify

- [x] 9.1 Run `uv run ruff check src tests` — no lint errors
- [x] 9.2 Run `uv run mypy src` — no type errors
- [x] 9.3 Run `uv run pytest tests/` — all tests pass
