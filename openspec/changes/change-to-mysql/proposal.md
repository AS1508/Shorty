## Why

The current system defaults to PostgreSQL (`asyncpg`), but the target environment uses MySQL. Switching the default driver and connection URL from Postgres to MySQL removes a dependency that isn't needed and makes the service boot out-of-the-box against the intended database.

## What Changes

- Replace the async DB driver from `asyncpg` to `aiomysql` in `pyproject.toml`.
- Update the default `DATABASE_URL` in `src/infra/config.py` from `postgresql+asyncpg://...:5432/...` to `mysql+aiomysql://...:3306/...`.
- Update the default `sqlalchemy.url` in `alembic.ini` to match.
- Update `README.md` docs.

No changes to models, repositories, use cases, routes, tests, or migration logic — SQLAlchemy abstracts the dialect differences entirely at this layer.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

_None — no spec-level requirements change. Every requirement in the `url-shortening` spec is DB-agnostic. The switch from Postgres to MySQL is purely an implementation/driver detail with no observable behavioral difference._

## Impact

- **Dependencies:** `asyncpg` removed, `aiomysql` added.
- **Configuration:** the default `DATABASE_URL` changes port and driver prefix. Existing deployments using a custom `DATABASE_URL` are unaffected.
- **Migrations:** the existing migration `0fdaf0c9d906` is portable (SQLAlchemy compiles `op.create_table` to correct DDL for the target engine). Re-run `alembic upgrade head` against the MySQL instance.
- **Tests:** zero impact. Integration tests use `sqlite+aiosqlite:///:memory:`, unit tests are pure logic.
- **Docs:** `README.md` updated. The `CHANGELOG` or equivalent should note this as an infrastructure change, not a feature change.
