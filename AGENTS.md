# Shorty — Agent Guide

URL shortener (Python/FastAPI backend + TypeScript/React/Vite frontend, PostgreSQL/Redis). Repo is greenfield: only `main.py` (hello world) and `pyproject.toml` exist. No `src/`, no `tests/`, no frontend, no Dockerfile, no CI.

## Spec-driven workflow (OpenSpec)

The repo uses [OpenSpec](openspec/) for spec-driven development (`openspec/config.yaml` → `schema: spec-driven`). The `openspec` CLI is installed.

Order for any non-trivial change:

1. `/opsx-explore` — think through the problem; read files, ask questions. No code.
2. `/opsx-propose <kebab-name>` — generates `proposal.md`, `design.md`, `tasks.md` under `openspec/changes/<name>/`.
3. Wait for explicit user "ok" on the plan before coding.
4. `/opsx-apply <name>` — implement the tasks in order.
5. `/opsx-archive <name>` — finalize once all tasks pass.

Skills: `.opencode/skills/openspec-{explore,propose,apply,archive}-change/`. Do not edit `openspec/specs/` directly — it is updated via `archive`.

## Toolchain

- Python 3.12, pinned in `.python-version` and `pyproject.toml` `requires-python`.
- `uv` for Python deps and the venv (not pip/poetry). The on-disk `.venv` exists but is empty.
- `npm` for the planned frontend.
- No pytest, mypy, ruff, or FastAPI installed yet. Add with `uv add` when needed.

## Target layout (create as you go)

- `src/api/` — FastAPI controllers and routes.
- `src/core/` — use cases and business logic (Snowflake, Base62 ID generation).
- `src/infra/` — DB / cache adapters (PostgreSQL, Redis).
- `tests/` — pytest, split into unit and integration.

## Conventions

Coding conventions (strict typing, `async/await` only in FastAPI, no `any` in TS, no secrets in code, no truncated code stubs, no `Dockerfile`/`docker-compose.yml` edits without explicit request, Conventional Commits, 3-attempt self-fix on test failures, plan-and-ask before coding) are auto-loaded from `.opencode/AGENTS.md`. Do not duplicate them here; do not "fix" them in PRs.

## Commands

- `uv run python main.py` — run the current entrypoint.
- `uv add <pkg>` / `uv add --dev <pkg>` — add deps.
- `uv run pytest` / `uv run mypy src` — only after those tools are added.
- `openspec list` / `openspec view` — inspect current specs and changes.

## Gotchas

- `README.md` is empty; do not assume documentation exists.
- `openspec/changes/` and `openspec/specs/` are empty placeholders.
- `.venv/` is committed-by-convention but ignored by `.gitignore`; use `uv` against it, do not recreate.
- No frontend `package.json`, no CI workflow, no infra config — only create what the change requires.
