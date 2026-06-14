## 1. Database schema and domain model

- [x] 1.1 Create Alembic migration `add_deleted_at_to_urls` adding `deleted_at TIMESTAMP WITH TIME ZONE NULL` to the `urls` table and creating index `ix_urls_deleted_at`
- [x] 1.2 Update the SQLAlchemy `Url` model in `src/infra/db/models.py` to include the `deleted_at` column mapped to `DateTime(timezone=True)` (nullable)
- [x] 1.3 Add `deleted_at: datetime | None = None` to the `UrlRecord` frozen dataclass in `src/core/ports.py` and update the `slots` order to keep it last for diff hygiene
- [x] 1.4 Update `SqlAlchemyUrlRepository` mapping in `src/infra/db/repository.py` so both `insert` and `find_by_id` round-trip the new `deleted_at` field (read and write both directions)

## 2. Cache port: add delete primitive

- [x] 2.1 Add `delete(self, key: str) -> None` to the `CachePort` protocol in `src/core/ports.py`
- [x] 2.2 Implement `delete` in the Redis adapter `src/infra/cache/redis.py` by issuing a single `DEL` command wrapped in fail-open error handling (return `None` on connection errors, do not raise)
- [x] 2.3 Implement `delete` in the in-memory cache fake used by the integration tests (look up the existing fake in `tests/` and extend it)

## 3. Repository: soft_delete method

- [x] 3.1 Add `soft_delete(self, id: int) -> int` to the `UrlRepository` protocol in `src/core/ports.py` returning the number of rows affected (0 or 1)
- [x] 3.2 Implement `soft_delete` in `SqlAlchemyUrlRepository` as a single `UPDATE urls SET deleted_at = :now WHERE id = :id AND deleted_at IS NULL` statement; commit and return the rowcount

## 4. Resolve pipeline: DELETED status

- [x] 4.1 Add a `DELETED` member to the `ResolveStatus` enum in `src/core/usecases/resolve_url.py`
- [x] 4.2 Add a `DELETED` sentinel value to the cache sentinels used by `ResolveURL` (e.g. a module-level constant like `__DELETED__`) and define a TTL constant for it (300 seconds, matching the blocked/expired sentinels)
- [x] 4.3 Update `ResolveURL.execute` to evaluate `deleted_at` after the `is_blocked` check and before the `expires_at` check, returning `DELETED` (mapped to `410 Gone` at the route layer) when the field is non-NULL; also write the `DELETED` sentinel to the cache on a fresh DB read
- [x] 4.4 Update the redirect route handler `src/api/routes/redirect.py` to map the new `DELETED` status to HTTP `410` with a body `{"detail": "This short link is gone"}`

## 5. Cleanup worker: 30-day purge

- [x] 5.1 Add a module-level constant `SOFT_DELETE_PURGE_DAYS = 30` in `src/core/expiration.py` (or a sibling module if more appropriate)
- [x] 5.2 Add a new repository method `delete_soft_deleted_older_than(days: int) -> int` to `UrlRepository` and implement it as `DELETE FROM urls WHERE deleted_at IS NOT NULL AND deleted_at <= now() - interval '<days> days'`
- [x] 5.3 Update the cleanup loop in `src/api/main.py` lifespan to run the new `delete_soft_deleted_older_than(SOFT_DELETE_PURGE_DAYS)` query in the same hourly cycle, independently of the existing expiration query (each in its own transaction)

## 6. Use case: SoftDeleteMyUrl

- [x] 6.1 Create `src/core/usecases/soft_delete_my_url.py` defining a `SoftDeleteMyUrl` class that depends on `UrlRepository` and `CachePort` (constructor-injected) and a `url_cache_key` callable (or constant) used to compute the Redis key from a Snowflake id
- [x] 6.2 Implement `SoftDeleteMyUrl.execute(short_code: str, current_user: str) -> None` that decodes the short code with `base62.decode`, looks up the URL via `repository.find_by_id`, returns silently (the route maps this to 404) when the record is missing, the owner does not match, or `deleted_at` is already set, otherwise calls `repository.soft_delete(id)` and `cache.delete(url_cache_key(id))` (ignoring cache errors)
- [x] 6.3 Register `SoftDeleteMyUrl` in `src/core/usecases/__init__.py` if other use cases are exported there (follow the existing pattern)

## 7. Rate limiting: my-urls bucket

- [x] 7.1 Add `rate_limit_my_urls_count: int = 60` and `rate_limit_my_urls_window_seconds: int = 60` to `src/infra/config.py` Settings
- [x] 7.2 Update `FixedWindowRateLimiter` in `src/core/rate_limit.py` (or the dependency wiring in `src/api/dependencies.py`) to accept a `bucket` argument so the same limiter instance can key on `rate:create:{email}`, `rate:redirect:{ip}`, or `rate:my_urls:{email}`; refactor the existing dependencies to pass the bucket explicitly
- [x] 7.3 Add a new `MyUrlsRateLimitDep` factory in `src/api/dependencies.py` that returns a `FixedWindowRateLimiter` configured with `bucket="my_urls"`, `count=settings.rate_limit_my_urls_count`, `window=settings.rate_limit_my_urls_window_seconds`, keyed by the authenticated user's email

## 8. API route: my_urls.py

- [x] 8.1 Create `src/api/routes/my_urls.py` with a FastAPI `APIRouter` and a single handler `delete_my_url(short_code: str, ...)` returning `Response(status_code=204)`
- [x] 8.2 In the handler, validate the short code against the Base62 regex (reuse the existing constant from the redirect route) and return 400 with a descriptive body on failure; otherwise call `SoftDeleteMyUrl.execute` and return 204
- [x] 8.3 Wire the route dependencies: `require_authenticated_user` for auth, `MyUrlsRateLimitDep` for throttling, and the new use case via a `SoftDeleteMyUrlDep` factory in `src/api/dependencies.py`

## 9. Wire up the new route and update redirect integration

- [x] 9.1 Register the new `my_urls` router in `src/api/main.py` (`app.include_router(my_urls.router)`)
- [x] 9.2 Verify that the redirect route still maps all four statuses (`OK`, `NOT_FOUND`, `BLOCKED`, `EXPIRED`) correctly and that the new `DELETED` status is mapped to 410; add a smoke test if one is missing

## 10. Tests

- [x] 10.1 Add unit tests in `tests/unit/test_soft_delete_my_url.py` covering: happy path, missing record (no exception raised), ownership mismatch, already-deleted (idempotent), invalid short code (raises a typed error), and cache-delete error is swallowed
- [x] 10.2 Add unit tests in `tests/unit/test_resolve_url.py` for the new `DELETED` branch: fresh DB read, cache hit on `DELETED` sentinel, and that `DELETED` takes precedence over `EXPIRED` when both fields are set
- [x] 10.3 Add unit tests in `tests/unit/test_expiration.py` for the new `SOFT_DELETE_PURGE_DAYS` constant and the soft-deleted cleanup query (mock the repository)
- [x] 10.4 Add integration tests in `tests/integration/test_my_urls_delete.py` covering the 13 scenarios from the SPEC-01 test plan (own URL, others' URL, non-existent, already-deleted, no auth, invalid code, cache invalidation, redirect returns 410, blocked URL deletable, expired URL deletable, concurrent deletes, cleanup-after-30-days, cleanup-keeps-recent)
- [x] 10.5 Update the existing integration tests in `tests/integration/test_redirect.py` to cover the new `410` path for soft-deleted URLs

## 11. Quality gates and commit

- [x] 11.1 Run `uv run ruff check src tests` and fix any lint findings
- [x] 11.2 Run `uv run mypy src tests` and resolve any type errors (especially around the new `CachePort.delete` and `UrlRepository.soft_delete` protocol members)
- [x] 11.3 Run `uv run pytest` and ensure all unit and integration tests pass
- [x] 11.4 Create a conventional commit `feat: add user URL soft delete` (or follow the project's commit convention if different) capturing the migration, the new endpoint, the redirect 410 behavior, and the cleanup query
