## 1. Configuration

- [x] 1.1 Add `rate_limit_create_count`, `rate_limit_create_window_seconds`, `rate_limit_redirect_count`, `rate_limit_redirect_window_seconds` fields to `Settings` in `src/infra/config.py` with type validation (positive ints) and defaults (20, 3600, 100, 60)

## 2. Redis Infrastructure

- [x] 2.1 Add `incr(key: str) -> int | None` method to `RedisCache` in `src/infra/cache/redis.py` — atomic INCR with fail-open (return `None` on error, log warning)
- [x] 2.2 Add unit test for `RedisCache.incr` covering successful increment, connection error, and general exception

## 3. Core Rate Limiting Logic

- [x] 3.1 Create `src/core/rate_limit.py` with `FixedWindowRateLimiter` class that encapsulates: calculation of window timestamp, Redis key construction, INCR + EXPIRE sequence, threshold check, `Retry-After` calculation, and IP extraction from `X-Forwarded-For`
- [x] 3.2 Add unit tests for `FixedWindowRateLimiter`: within limit, at limit, exceeding limit, new window resets counter, retry-after calculation, IP extraction (single proxy, multiple proxies, no proxy header, IPv6)

## 4. FastAPI Dependencies

- [x] 4.1 Add `require_rate_limit_create(state, request, authenticated_user)` dependency in `src/api/dependencies.py` — checks creation rate limit, raises `HTTPException(429)` on threshold, fail-open on Redis error
- [x] 4.2 Add `require_rate_limit_redirect(state, request)` dependency in `src/api/dependencies.py` — checks redirect rate limit, extracts IP, raises `HTTPException(429)` on threshold, fail-open on Redis error
- [x] 4.3 Wire `RateLimitCreateDep` and `RateLimitRedirectDep` type annotations in `src/api/dependencies.py`

## 5. Route Integration

- [x] 5.1 Inject `RateLimitCreateDep` into `POST /Create-URL` handler in `src/api/routes/shortener.py` (after auth, before handler logic)
- [x] 5.2 Inject `RateLimitRedirectDep` into `GET /{short_code}` handler in `src/api/routes/redirect.py` (before short code validation)

## 6. Integration Tests

- [x] 6.1 Integration test: `POST /Create-URL` within limit returns 201, exceeding limit returns 429
- [x] 6.2 Integration test: `POST /Create-URL` window boundary resets counter
- [x] 6.3 Integration test: `POST /Create-URL` fail-open when Redis is down
- [x] 6.4 Integration test: `POST /Create-URL` without auth still returns 403 (not 429)
- [x] 6.5 Integration test: `GET /{short_code}` within limit resolves normally (302/404/410)
- [x] 6.6 Integration test: `GET /{short_code}` exceeding limit returns 429
- [x] 6.7 Integration test: `GET /{short_code}` fail-open when Redis is down
- [x] 6.8 Integration test: `GET /{short_code}` different IPs have independent counters
- [x] 6.9 Integration test: verify `Retry-After` header is present in 429 responses

## 7. Verification

- [x] 7.1 Run existing test suite: `uv run pytest` — all tests pass (no regressions)
- [x] 7.2 Run linter and type checker: `uv run ruff check src/ tests/` and `uv run mypy src/` — clean

## 8. Commit

- [ ] 8.1 Conventional commit: `feat: add rate limiting for URL creation (by user) and redirection (by IP)`
