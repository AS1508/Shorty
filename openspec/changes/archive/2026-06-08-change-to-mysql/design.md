## Context

The service currently hardcodes a PostgreSQL connection URL as its default `DATABASE_URL` and lists `asyncpg` as a runtime dependency. The target deployment uses MySQL. Because the entire persistence layer is built on SQLAlchemy (models, repository, Alembic), the ORM already abstracts dialect differences — no model definitions, queries, or data types need to change.

## Goals / Non-Goals

**Goals:**
- Replace the default `DATABASE_URL` from `postgresql+asyncpg://...` to `mysql+aiomysql://...`.
- Replace the `asyncpg` dependency with `aiomysql` in `pyproject.toml`.
- Update `alembic.ini` default URL.
- Update `README.md` documentation.
- Confirm the existing migration `0fdaf0c9d906_create_urls_table.py` runs correctly against MySQL.

**Non-Goals:**
- No changes to SQLAlchemy models, repository code, use cases, routes, or tests.
- No data migration; this assumes a fresh database (the service has no production data).
- No spec-level behavior changes — every observable requirement remains identical.

## Decisions

### Driver: `aiomysql` over `asyncmy`

`aiomysql` is the older, more mature async MySQL driver with the widest SQLAlchemy async support and documentation. `asyncmy` is faster (C extension) but has a smaller community. Both expose the same connection URL prefix (`mysql+aiomysql://` / `mysql+asyncmy://`). We choose `aiomysql` for compatibility and ease of debugging.

### Porting the migration

The existing migration `0fdaf0c9d906` uses only portable SQLAlchemy constructs: `BigInteger`, `Text`, `DateTime(timezone=True)`, `CheckConstraint`, `func.now()`. These compile to correct MySQL DDL when `alembic upgrade head` is run against a MySQL connection. No migration rewrite is needed — only a re-run.

### CHECK constraint support

MySQL ≥ 8.0.16 enforces CHECK constraints. The migration includes `length(original_url) <= 2048`. On MySQL < 8.0.16 the constraint is parsed and ignored — our Python validation in the route layer already prevents oversized URLs, so the gap has no practical impact.

### No other code changes

- **`src/infra/db/models.py`**: `BigInteger`, `DateTime`, `Text`, `CheckConstraint` — all portable.
- **`src/infra/db/repository.py`**: Pure SQLAlchemy, no Postgres-specific features.
- **`src/api/dependencies.py`**: Builds the engine from `DATABASE_URL` — no dialect-specific logic.
- **`alembic/env.py`**: Uses `async_engine_from_config` — compatible with any SQLAlchemy async driver.
- **Tests**: `sqlite+aiosqlite:///:memory:` — unchanged.

## Risks / Trade-offs

- **[MySQL < 8.0.16] CHECK ignored silently** → Mitigated by app-level validation (route checks URL length).
- **[`aiomysql` maturity]**
- **The 4 files**:
  `pyproject.toml` (deps)
  `src/infra/config.py` (default URL)
  `alembic.ini` (default URL)
  `README.md` (documentation)
- **Setup**: `uv sync`, `alembic upgrade head`, `uv run shorty` — same workflow as before.
- **Rollback**: revert the 4 files and run `uv add asyncpg && uv remove aiomysql`.
