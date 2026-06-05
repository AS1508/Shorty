## 1. Configuration

- [x] 1.1 Add `proxy_shared_secret: str` field to `Settings` in `src/infra/config.py` (default empty string, read from `PROXY_SHARED_SECRET` env var).

## 2. Model and data layer

- [x] 2.1 Add `created_by: str | None` to `UrlRecord` dataclass in `src/core/ports.py`.
- [x] 2.2 Add `created_by: Mapped[str | None]` column (nullable `String(254)`) to `Url` model in `src/infra/db/models.py`.
- [x] 2.3 Update `SqlAlchemyUrlRepository.insert` in `src/infra/db/repository.py` to persist `created_by` when present.

## 3. Auth dependency

- [x] 3.1 Implement `require_authenticated_user(request: Request, settings: SettingsDep) -> str` in `src/api/dependencies.py`: reads `X-Authenticated-User` header, validates format, verifies HMAC-SHA256 signature against `X-Auth-Signature` using `PROXY_SHARED_SECRET` (skipped when secret is empty), raises `403 Forbidden` on failure.
- [x] 3.2 Define `AuthenticatedUserDep = Annotated[str, Depends(require_authenticated_user)]` and wire it into `POST /Create-URL` in `src/api/routes/shortener.py`, passing the email to the use case.
- [x] 3.3 Update `CreateShortURL.execute` in `src/core/usecases/create_short_url.py` to accept an optional `created_by: str | None` parameter and pass it through to the repository.

## 4. Database migration

- [x] 4.1 Generate Alembic migration for the `created_by` column: `alembic revision --autogenerate -m "add created_by to urls"`.
- [x] 4.2 Apply migration against MySQL: `DATABASE_URL="mysql+aiomysql://..." uv run alembic upgrade head`.

## 5. Tests

- [x] 5.1 Add integration test: `POST /Create-URL` without `X-Authenticated-User` returns `403`.
- [x] 5.2 Add integration test: `POST /Create-URL` with empty `X-Authenticated-User` returns `403`.
- [x] 5.3 Add integration test: `POST /Create-URL` with invalid email format in `X-Authenticated-User` returns `403`.
- [x] 5.4 Add integration test: `POST /Create-URL` with valid `X-Authenticated-User` but missing `X-Auth-Signature` returns `403` (when secret is set).
- [x] 5.5 Add integration test: `POST /Create-URL` with valid `X-Authenticated-User` but wrong `X-Auth-Signature` returns `403`.
- [x] 5.6 Update existing integration tests for `POST /Create-URL` to include valid `X-Authenticated-User` + `X-Auth-Signature` headers.
- [x] 5.7 Verify `GET /{short_code}` still works without any auth headers (no regression).

## 6. Verification

- [x] 6.1 Run `uv run ruff check src tests && uv run mypy src tests && uv run pytest` — all green.
- [x] 6.2 Smoke test: boot app against MySQL, create URL with valid `X-Authenticated-User` + `X-Auth-Signature` via curl, verify `created_by` is persisted.
- [x] 6.3 Smoke test: verify that forging an invalid signature returns `403`.

## 7. Commit

- [x] 7.1 Conventional Commits: `feat: add HMAC-signed proxy auth via X-Authenticated-User header for POST /Create-URL`.
