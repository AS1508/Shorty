## 1. Entrypoint

- [ ] 1.1 Create `passenger_wsgi.py` at project root with venv re-exec and ASGI entrypoint

## 2. Dependencies

- [ ] 2.1 Generate `requirements.txt` via `uv pip compile pyproject.toml -o requirements.txt`

## 3. Passenger restart mechanism

- [ ] 3.1 Create `tmp/restart.txt` placeholder file

## 4. Documentation

- [ ] 4.1 Create `DEPLOY.md` with step-by-step cPanel deploy guide (prerequisites, Application Manager, env vars, MySQL, Redis, migrations, verification)

## 5. Integration check

- [ ] 5.1 Simulate Passenger load: verify `passenger_wsgi.py` exports `application` correctly

## 6. Verify

- [ ] 6.1 Run `uv run ruff check .` — no lint errors
- [ ] 6.2 Run `uv run mypy src` — no type errors
- [ ] 6.3 Run `uv run pytest tests/` — all tests pass
