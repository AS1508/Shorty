## 1. Database Schema

- [x] 1.1 Add `expires_at TIMESTAMP WITH TIME ZONE NOT NULL` column to `urls` table via migration
- [x] 1.2 Create index on `expires_at` for efficient cleanup queries
- [x] 1.3 Update SQLAlchemy/ORM model to include `expires_at` field

## 2. Expiration Core Logic

- [x] 2.1 Define `URL_TTL_SECONDS = 5_184_000` as a module-level constant in `src/core/`
- [x] 2.2 Implement `calculate_expires_at(created_at: datetime) -> datetime` function that adds 60 days in UTC
- [x] 2.3 Implement `is_expired(expires_at: datetime) -> bool` helper comparing against `datetime.now(UTC)`
- [x] 2.4 Implement background cleanup worker: an asyncio loop that runs every `CLEANUP_INTERVAL_SECONDS` (default 3600), deletes rows where `expires_at <= now(UTC)`, integrated via FastAPI lifespan

## 3. URL Redirection Endpoint

- [x] 3.1 Create `GET /<code>` route in `src/api/` that validates short code format against `[A-Za-z0-9]+`
- [x] 3.2 Implement cache-first resolution: check Redis for `code -> original_url`, redirect with 302 on hit
- [x] 3.3 On cache miss, query database by short code (Base62-decode to Snowflake ID), check `expires_at`
- [x] 3.4 Return `302 Found` with `Location` header for valid non-expired URLs
- [x] 3.5 Return `410 Gone` with `{"detail": "This short link has expired"}` when `expires_at <= now(UTC)`
- [x] 3.6 Return `404 Not Found` with `{"detail": "Short link not found"}` for unknown codes
- [x] 3.7 On cache miss with valid record, rehydrate Redis cache with TTL = `expires_at - now(UTC)` seconds

## 4. Modify Shortening Endpoint

- [x] 4.1 Update `POST /Create-URL` handler to compute `expires_at` via `calculate_expires_at(created_at)`
- [x] 4.2 Persist `expires_at` in the `urls` table alongside `created_at`, `created_by`, Snowflake ID, and original URL
- [x] 4.3 Set Redis key TTL to `URL_TTL_SECONDS` via `EXPIRE` after `SET` on the short code cache entry
- [x] 4.4 Implement expired shortcode collision resolution: if generated code matches an existing row with `expires_at <= now(UTC)`, delete the expired row and insert the new record

## 5. Tests

- [x] 5.1 Unit test `test_calculate_expiration_date`: verify the function returns `now + 60 days` in UTC, including leap year boundary
- [x] 5.2 Unit test `test_is_expired`: verify `True` when `expires_at` is in the past, `False` when in the future
- [x] 5.3 Integration test `test_create_url_persists_expires_at`: POST a valid URL, verify the database row contains `expires_at` exactly 60 days after `created_at`
- [x] 5.4 Integration test `test_redirect_valid_url`: create a short link, GET the code, verify 302 status and correct `Location` header
- [x] 5.5 Integration test `test_redirect_expired_url`: create a short link, freeze/mock time to 60 days + 1 minute in the future, GET the code, verify HTTP 410 Gone
- [x] 5.6 Integration test `test_redirect_unknown_code`: GET a nonexistent code, verify 404 Not Found
- [x] 5.7 Integration test `test_redirect_invalid_code_format`: GET a code with special characters (e.g., `ab-cd`), verify 400 Bad Request
- [x] 5.8 Integration test `test_cleanup_worker_deletes_expired`: insert expired rows, trigger cleanup, verify they are deleted
- [x] 5.9 Integration test `test_collision_reuses_expired_code`: create and expire a URL, create a new URL that generates the same Snowflake code, verify 201 and new record persists
- [x] 5.10 Integration test `test_cache_ttl_set_on_creation`: verify Redis `TTL` matches `URL_TTL_SECONDS` after shortening
