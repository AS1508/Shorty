## Context

The repo is greenfield: only `main.py` (hello world) and `pyproject.toml` exist. No `src/` tree, no FastAPI app, no DB models, no migrations, no tests. The target architecture (per `AGENTS.md`) is hexagonal:

- `src/api/` — FastAPI controllers and routes
- `src/core/` — use cases and business logic (Snowflake, Base62)
- `src/infra/` — DB/cache adapters (PostgreSQL, Redis)

PostgreSQL is the chosen store; no connection string is committed — runtime config will come from environment variables (`DATABASE_URL`, `SNOWFLAKE_NODE_ID`, `SHORT_BASE_URL`). The Snowflake generator must be correct in a single-process MVP and safe enough to extend to multiple workers later.

## Goals / Non-Goals

**Goals:**

- Implement `POST /Create-URL` end-to-end (validate → generate ID → encode → persist → respond).
- Generate unique 64-bit IDs without DB round-trips.
- Produce short codes that are pure Base62 (alphanumeric, case-sensitive, URL-safe).
- Persist the `(id, original_url, created_at)` tuple atomically; never return a short URL whose row failed to write.
- Lay the hexagonal skeleton so the next change (redirect endpoint, analytics) plugs in cleanly.

**Non-Goals:**

- The redirect endpoint (`GET /{short_code}`), TTL/expiration, custom aliases, auth, rate limiting, analytics — all deferred.
- Distributed coordination of Snowflake across multiple processes (the MVP runs as one process; node ID is taken from `SNOWFLAKE_NODE_ID` env var, with a documented extension path to a Redis-backed lease later).
- URL safety checks (malware, phishing, denylists) — out of scope for the MVP.

## Decisions

### Snowflake bit layout: 41 / 10 / 12

- **41 bits** for millisecond timestamp → usable until year ~2109.
- **10 bits** for node/worker ID → up to 1024 distinct workers in a future multi-process deployment.
- **12 bits** for sequence within the same millisecond → 4096 IDs/ms/worker.

Rationale: this is the same layout Twitter used (modulo the 1-bit sign). It gives 4096 IDs per ms per worker, which is far above the expected single-worker QPS for the MVP. 10-bit node leaves room to grow without redesigning the bit layout.

### Sequence exhaustion handling: block (spin) until next millisecond

If `seq` rolls over within one millisecond, the generator loops calling `time.sleep(0)` (yield) until `now_ms > last_ms`, then resets the sequence. This is correct and bounded — it cannot deadlock because real time always advances.

Alternatives considered:

- Reject the request with `503` on exhaustion → simpler, but would lose user traffic at peak. Not chosen for MVP.
- Pre-allocate a batch of IDs at startup → complicates persistence (need to track allocations) without buying anything at MVP QPS. Deferred.

### Clock drift handling: raise `InvalidSystemClock`

If `now_ms < last_ms`, the generator raises `InvalidSystemClock` and stops emitting IDs until the operator intervenes. We never silently issue a duplicate by reusing a past timestamp.

### Node ID source: `SNOWFLAKE_NODE_ID` env var (default 0)

For the single-process MVP, a static env var is enough. The generator reads it at startup and validates `0 <= node_id < 1024`. The path to multi-process (one worker per pod) requires a startup lease (e.g., Redis `SET NX EX`) — documented as a follow-up; no code for it here.

### Base62 alphabet: `0-9A-Za-z` (digit-first, big-endian)

`encode(int) -> str` and `decode(str) -> int` are exact inverses. The digit-first ordering keeps the alphabet stable and easy to inspect. We never pad; outputs are variable length (typical codes: 6–9 chars for IDs in the 10^17–10^18 range).

### URL validation: Pydantic `HttpUrl` + length cap

The request body uses a Pydantic model with `url: HttpUrl`, which rejects malformed schemes, missing hosts, etc. A second check enforces `len(url) <= 2048` to match the conventional browser/server limit. Anything failing either check returns `400` with a descriptive `detail` string.

### Persistence: SQLAlchemy 2.0 async + asyncpg

- `urls` table: `id BIGINT PRIMARY KEY`, `original_url TEXT NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- An index on `id` (the PK already provides it) and a check on `original_url` length at the DB level (`CHECK (char_length(original_url) <= 2048)`).
- The repository inserts the row inside the same async transaction the request handler is in; if `INSERT` raises, the request returns `500` and no short URL is exposed.

### Error model: HTTPException with semantic codes

- `400 Bad Request` — invalid/malformed URL, oversize URL, missing body field.
- `500 Internal Server Error` — persistence failure or `InvalidSystemClock` propagated (clock-drift is a server fault, not a client fault).

### Layered call flow

```
HTTP (FastAPI route)
  → Pydantic request validation (in router)
  → use case: CreateShortURL (src/core/usecases/create_short_url.py)
      ├── SnowflakeGenerator.next_id()           (src/core/snowflake.py)
      └── Base62.encode(id)                      (src/core/base62.py)
  → URLRepository.insert(...)                    (src/infra/db/repository.py)
  → return { short_url: f"{base_url}/{code}" }
```

The route never imports the DB driver or the generator directly; it goes through the use case, which depends on abstract ports (`UrlRepository`, `IdGenerator`) injected at app startup. This keeps `src/core/` free of framework/DB imports and testable in isolation.

## Risks / Trade-offs

- **Single-process Snowflake** → horizontal scaling requires a node-ID lease. Mitigation: node ID is configurable; the layout supports 1024 workers without code change, only an init hook.
- **Clock-drift detection stops the service** → a real NTP step backward takes the endpoint offline until clocks align. Mitigation: emit a structured log and a `/healthz` signal; an operator can restart with a forced `last_ms` reset. Acceptable for MVP; revisit with monotonic clock APIs if it becomes a problem.
- **No URL safety/denylist** → the service can be used to shorten phishing URLs. Mitigation: defer to a follow-up change; document as a known gap.
- **No retry on transient DB failures** → a flaky network drops the request. Mitigation: keep the request handler tight; rely on asyncpg's internal pooling; add retry/idempotency in a later change.
- **No observability** → no metrics, no tracing, no request logs beyond uvicorn defaults. Mitigation: deferred to an `observability` capability change.

## Migration Plan

This is the first persistent change, so we bootstrap Alembic as part of it:

1. Add `urls` table via a single initial migration (`alembic revision --autogenerate -m "create urls table"`).
2. Deploy steps (when there is something to deploy): apply migrations against the target DB, restart the FastAPI process.
3. Rollback: `alembic downgrade -1` drops the `urls` table. No data-loss risk on a greenfield service.

## Open Questions

- **Public host for the short URL.** The MVP returns `https://<SHORT_BASE_URL>/<code>`. The exact production hostname and HTTPS termination story (uvicorn behind nginx? a managed LB?) are TBD and owned by a future `deployment` change.
- **Node ID assignment in production.** For now: operator-set env var. A future change will lease IDs from Redis at pod start.
- **ID column type in SQLAlchemy.** Plan is `BigInteger` mapped to `BIGINT` in PostgreSQL. Will confirm during implementation that asyncpg returns the BIGINT as Python `int` (not as `decimal.Decimal`) — if not, we'll cast at the repository boundary.
