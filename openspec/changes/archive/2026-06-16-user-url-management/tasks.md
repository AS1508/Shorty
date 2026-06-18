## 1. Core — Repository Layer

- [x] 1.1 Add `find_all_by_created_by(created_by, cursor, limit)` protocol method to `UrlRepository` in `src/core/ports.py`
- [x] 1.2 Implement `find_all_by_created_by` in `SqlAlchemyUrlRepository` at `src/infra/db/repository.py`

## 2. Core — Use Cases

- [x] 2.1 Create `ListMyUrls` use case in `src/core/usecases/list_my_urls.py` with cursor pagination and `is_expired` computation
- [x] 2.2 Create `GetMyUrl` use case in `src/core/usecases/get_my_url.py` with ownership verification

## 3. API — Dependencies & Wiring

- [x] 3.1 Add `get_list_my_urls` and `get_my_url` factory functions in `src/api/dependencies.py`
- [x] 3.2 Add type aliases `ListMyUrlsDep` and `GetMyUrlDep` for FastAPI injection

## 4. API — Routes

- [x] 4.1 Add `GET /my-urls` handler to `src/api/routes/my_urls.py` with cursor/limit parsing, auth, rate limit, and response DTO construction
- [x] 4.2 Add `GET /my-urls/{short_code}` handler to `src/api/routes/my_urls.py` with Base62 validation, auth, rate limit, and response DTO

## 5. Tests — Unit

- [x] 5.1 Write `tests/unit/test_list_my_urls.py` covering empty list, single page, multi-page pagination, cursor edge cases, and other-user isolation
- [x] 5.2 Write `tests/unit/test_get_my_url.py` covering own URL found, not found, other user, deleted, expired, blocked

## 6. Tests — Integration

- [x] 6.1 Write `tests/integration/test_my_urls_list_endpoint.py` covering happy path, pagination, auth rejection, rate limiting, expired/deleted URLs in list
- [x] 6.2 Write `tests/integration/test_my_urls_detail_endpoint.py` covering own URL detail, other user URL, nonexistent, invalid code, unauthenticated, rate limited, expired/blocked/deleted states

## 7. Verify

- [x] 7.1 Run `uv run ruff check src tests` — no lint errors
- [x] 7.2 Run `uv run mypy src` — no type errors
- [x] 7.3 Run `uv run pytest tests/` — all tests pass
