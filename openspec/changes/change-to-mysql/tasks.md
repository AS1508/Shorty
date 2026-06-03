## 1. Switch driver

- [ ] 1.1 Replace `asyncpg` with `aiomysql` in `pyproject.toml` (`uv add aiomysql && uv remove asyncpg`).
- [ ] 1.2 Update default `DATABASE_URL` in `src/infra/config.py` to `mysql+aiomysql://shorty:shorty@localhost:3306/shorty`.
- [ ] 1.3 Update default `sqlalchemy.url` in `alembic.ini` to match.

## 2. Verify

- [ ] 2.1 Run `uv run ruff check src tests`, `uv run mypy src tests`, `uv run pytest` — all green.
- [ ] 2.2 Re-run migration against MySQL (`DATABASE_URL="mysql+aiomysql://..." uv run alembic upgrade head`) and confirm table is created.
- [ ] 2.3 Update `README.md` (default `DATABASE_URL` value, driver prerequisite).
- [ ] 2.4 Smoke test: boot the app against MySQL and exercise `POST /Create-URL` with `curl`.

## 3. Commit

- [ ] 3.1 Conventional Commits: `feat: switch database driver from PostgreSQL to MySQL (aiomysql)`.
