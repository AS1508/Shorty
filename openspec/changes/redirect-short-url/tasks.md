## 1. Core: resolve URL use case

- [x] 1.1 Add `UrlRepository.find_by_id(id: int) -> UrlRecord | None` to the port interface in `src/core/ports.py`.
- [x] 1.2 Implement `find_by_id` in `SqlAlchemyUrlRepository` (simple async query by PK).
- [x] 1.3 Implement `ResolveURL` use case in `src/core/usecases/resolve_url.py`: takes `(code: str, id_generator not needed — just decode Base62 + repository + cache)`. Returns a result object with `(status: ok|not_found|blocked, url: str|None)`.

## 2. Cache adapter

- [x] 2.1 Add `redis-py` dependency: `uv add redis`.
- [x] 2.2 Add `REDIS_URL` to `Settings` in `src/infra/config.py` (default `redis://localhost:6379/0`).
- [x] 2.3 Define `CachePort` protocol in `src/core/ports.py` with `get(key) -> str | None` and `set(key, value, ttl)`.
- [x] 2.4 Implement `RedisCache` in `src/infra/cache/redis.py` using `redis.asyncio.Redis`; wrap every call in `try/except ConnectionError` for graceful degradation.
- [x] 2.5 Implement negative/blocked sentinel encoding (JSON `{\"s\":\"ok\",\"u\":\"...\"}`, `{\"s\":\"null\"}`, `{\"s\":\"blocked\"}`) in a shared cache value helper.

## 3. DB model + migration: is_blocked

- [x] 3.1 Add `is_blocked: Mapped[bool]` column to `Url` model (default `False`).
- [x] 3.2 Generate Alembic revision: `alembic revision --autogenerate -m "add is_blocked to urls"`.
- [x] 3.3 Apply migration: `alembic upgrade head` (verified both revisions applied cleanly to SQLite).

## 4. API: redirect route

- [x] 4.1 Implement the route in `src/api/routes/redirect.py`: `GET /{short_code}` → validate Base62 chars with regex → call `ResolveURL.execute` → return 302/404/403.
- [x] 4.2 Wire the route, cache adapter, and Redis pool into the app in `src/api/main.py` (lifespan + dependencies).
- [x] 4.3 Add `src/api/schemas.py` response models if needed (error body schemas).

## 5. Tests

- [x] 5.1 Unit test `ResolveURL` with fake repository + fake cache: success path, not-found path, blocked path, cache-hit path, cache-miss-then-db path.
- [x] 5.2 Unit test `RedisCache` graceful degradation: simulate `ConnectionError` and verify fall-through.
- [x] 5.3 Unit test: invalid Base62 code in route returns 400.
- [x] 5.4 Integration test: full redirect flow with httpx + FastAPI + SQLite + fake cache override.
- [x] 5.5 Integration test: non-existent code returns 404; second call is cache-served (no DB query).

## 6. Verification

- [x] 6.1 `uv run ruff check src tests && uv run mypy src tests && uv run pytest` — all green.
- [x] 6.2 Smoke test: boot app against a real Redis + MySQL, create URL then redirect with curl.
- [x] 6.3 Update `README.md` with Redis prerequisite, new env var, and endpoint example.

## 7. Commit

- [ ] 7.1 Conventional Commits: `feat: add GET /{short_code} redirect endpoint with Redis cache`.
