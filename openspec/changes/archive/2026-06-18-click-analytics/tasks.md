## 1. Database — Migration

- [x] 1.1 Add `clicks` column to `Url` model in `src/infra/db/models.py` (`BIGINT NOT NULL DEFAULT 0`)
- [x] 1.2 Generate Alembic migration: `uv run alembic revision --autogenerate -m "add clicks column"`
- [x] 1.3 Review and adjust the generated migration

## 2. Repository — Click increment

- [x] 2.1 Add `increment_clicks(id)` to `UrlRepository` protocol in `src/core/ports.py`
- [x] 2.2 Implement `increment_clicks` in `SqlAlchemyUrlRepository` (atomic `UPDATE clicks = clicks + 1`)
- [x] 2.3 Add `clicks: int = 0` field to `UrlRecord` dataclass and update `_row_to_record` mapping

## 3. Core — Increment on redirect

- [x] 3.1 Add `increment_clicks` call in `ResolveURL._resolve` after confirming OK status, with contextlib.suppress for errors

## 4. API — Expose clicks in responses

- [x] 4.1 Include `clicks` in `_build_item` helper in `src/api/routes/my_urls.py` (list and detail)
- [x] 4.2 Include `clicks` in admin list response (in `src/api/routes/admin.py`)

## 5. API — Admin stats endpoint

- [x] 5.1 Add `GET /admin/stats/{short_code}` handler in `src/api/routes/admin.py` with admin auth but no ownership check
- [x] 5.2 Wire `GetMyUrl`-style lookup without ownership filter for admin

## 6. Tests — Unit

- [x] 6.1 Write `tests/unit/test_click_counter.py` covering increment on OK, no increment on blocked/expired/deleted/not-found, silent failure

## 7. Tests — Integration

- [x] 7.1 Write `tests/integration/test_click_analytics.py` covering: redirect increments clicks, concurrent increments, clicks in my-urls list/detail, clicks in admin list, admin stats endpoint, non-admin stats rejection

## 8. Verify

- [x] 8.1 Run `uv run ruff check src tests` — no lint errors
- [x] 8.2 Run `uv run mypy src` — no type errors
- [x] 8.3 Run `uv run pytest tests/` — all tests pass
