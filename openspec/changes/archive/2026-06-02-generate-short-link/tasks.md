## 1. Project setup

- [x] 1.1 Add runtime dependencies: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic` via `uv add`.
- [x] 1.2 Add dev dependencies: `pytest`, `pytest-asyncio`, `httpx`, `mypy`, `ruff` via `uv add --dev`.
- [x] 1.3 Create the `src/` skeleton with empty `__init__.py` files in `src/api/`, `src/api/routes/`, `src/core/`, `src/infra/`, `src/infra/db/`, plus `tests/unit/` and `tests/integration/`.
- [x] 1.4 Add a `Settings` class in `src/infra/config.py` using `pydantic-settings` that reads `DATABASE_URL`, `SHORT_BASE_URL`, and `SNOWFLAKE_NODE_ID` from the environment (node ID defaults to `0`).
- [x] 1.5 Configure `pyproject.toml` for `ruff` (line length, target Python 3.12) and `mypy` (strict mode); add `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and the test paths.

## 2. Core: Snowflake ID generator

- [x] 2.1 Implement `SnowflakeGenerator` in `src/core/snowflake.py` with the 41/10/12 bit layout, custom epoch (e.g. `2024-01-01T00:00:00Z`), and a `next_id() -> int` method.
- [x] 2.2 Implement the sequence-exhaustion branch: spin on `last_ms` until the wall clock advances to a new millisecond.
- [x] 2.3 Define `InvalidSystemClock` exception and raise it when `now_ms < last_ms`.
- [x] 2.4 Write `tests/unit/test_snowflake.py` asserting (a) 10,000 calls produce distinct IDs, (b) `InvalidSystemClock` is raised when the wall clock is forced backwards (use a fake clock injectable into the generator).

## 3. Core: Base62 codec

- [x] 3.1 Implement `encode(int) -> str` and `decode(str) -> int` in `src/core/base62.py` using the alphabet `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`.
- [x] 3.2 Write `tests/unit/test_base62.py` asserting exact known encodings (e.g. `encode(0) == "0"`, `encode(62) == "10"`) and that `decode(encode(x)) == x` for a sweep of inputs (0, 1, 61, 62, 4095, 2**63 - 1).

## 4. Core: use case

- [x] 4.1 Define abstract ports `IdGenerator` (with `next_id`) and `UrlRepository` (with `insert(UrlRecord) -> None`) in `src/core/ports.py`.
- [x] 4.2 Implement the `CreateShortURL` use case in `src/core/usecases/create_short_url.py`: it takes `(id_generator, repository, base_url)`, generates an ID, encodes it, persists a record, and returns the full short URL.
- [x] 4.3 Write `tests/unit/test_create_short_url.py` with fake ports, asserting: success returns a short URL whose code decodes back to the generated ID, and a repository exception propagates without returning a URL.

## 5. Infra: DB models and repository

- [x] 5.1 Define the SQLAlchemy model in `src/infra/db/models.py`: table `urls` with `id: BigInteger` PK, `original_url: Text` (with `CHECK (length(original_url) <= 2048)` for SQLite/Postgres portability), `created_at: DateTime(timezone=True)` defaulting to `func.now()`.
- [x] 5.2 Implement `SqlAlchemyUrlRepository` in `src/infra/db/repository.py` using the async engine and session, mapping the model to the `UrlRecord` domain object.
- [x] 5.3 Write `tests/integration/test_repository.py` against a SQLite-in-memory or testcontainers Postgres instance; insert one row and assert it round-trips.

## 6. Infra: Alembic migration

- [x] 6.1 Initialize Alembic (`alembic init -t async alembic`), set `sqlalchemy.url` in `alembic/env.py` to read from the same `Settings.DATABASE_URL`, and configure `target_metadata` to the models' metadata.
- [x] 6.2 Generate the initial revision (`alembic revision --autogenerate -m "create urls table"`) and review the diff to confirm the `urls` table, the `CHECK` constraint, and no extras.
- [x] 6.3 Run `alembic upgrade head` against a local database (SQLite for the smoke check; same migration applies to Postgres) and verify the table is created.

## 7. API: routes and app wiring

- [x] 7.1 Define Pydantic schemas in `src/api/schemas.py`: `CreateURLRequest(url: HttpUrl)` and `CreateURLResponse(short_url: AnyHttpUrl)`; add a manual length check of `2048` on the original string.
- [x] 7.2 Implement the route in `src/api/routes/shortener.py`: `POST /Create-URL` → calls the use case → returns `201` with the response body, or raises `HTTPException(400/500)` with a `detail` string.
- [x] 7.3 Wire the FastAPI app in `src/api/main.py`: build the async engine, the repository, the Snowflake generator, the use case, and inject them into the route via a dependency provider.
- [x] 7.4 Add a `__main__` entrypoint (`uvicorn src.api.main:app --host 0.0.0.0 --port 8000`) and document it in `pyproject.toml` under `[project.scripts]` as `shorty = "src.api.main:run"`.

## 8. Tests: integration of the endpoint

- [x] 8.1 Write `tests/integration/test_create_url_endpoint.py` using `httpx.AsyncClient` with the FastAPI app; override the repository dependency with one backed by SQLite-in-memory.
- [x] 8.2 Assert the success path returns `201`, a parseable `short_url`, and the row exists in the DB.
- [x] 8.3 Assert the failure paths return `400` for: missing field, non-string value, scheme-less URL, oversize URL.

## 9. Verification

- [x] 9.1 Run `uv run ruff check src tests`, `uv run mypy src tests`, and `uv run pytest`; all green.
- [x] 9.2 Boot the app locally and exercise the endpoint with `curl`; smoke-tested with SQLite file + `alembic upgrade head` first (Postgres workflow is identical once `DATABASE_URL` points at a real instance). Sample response: `{"short_url":"http://localhost:8000/NdEmeHuf0C"}` (decodes back to Snowflake ID `319920320607682560`).
- [x] 9.3 Update `README.md` with: prerequisites (Python 3.12, `uv`, Postgres), how to run migrations, how to start the service, and a `curl` example for `POST /Create-URL`.

## 10. Commit

- [ ] 10.1 Conventional Commits: `feat: add POST /Create-URL endpoint with Snowflake + Base62`.
