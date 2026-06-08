## Why

Shortened URLs currently live forever with no expiration mechanism. This creates unbounded storage growth and means broken or stale links persist indefinitely. Adding a default 60-day automatic expiration ensures the system self-cleans, reduces storage pressure, and provides predictable link lifecycle semantics.

## What Changes

- **NEW**: Every created short URL automatically gets an `expires_at` timestamp set to `created_at + 60 days` (UTC).
- **NEW**: A GET redirection endpoint (`/<code>`) that resolves short codes and validates expiration before redirecting.
- **MODIFIED**: The `POST /Create-URL` endpoint now persists `expires_at` alongside the URL record.
- **NEW**: Expired URLs return HTTP `410 Gone` on resolution attempts.
- **NEW**: A background worker/cleanup job periodically purges expired records from the persistent database.
- **NEW**: Cache entries (Redis) use native TTL matching the 60-day window for automatic eviction.

## Capabilities

### New Capabilities

- `url-redirection`: HTTP GET endpoint at `/<code>` that resolves a short code, validates expiration, and redirects (301/302) to the original URL or returns 410 Gone if expired.
- `url-expiration`: Automatic calculation of `expires_at` (creation time + 60 days UTC) at short-link creation, with lazy validation at read time and periodic background cleanup of expired database records.

### Modified Capabilities

- `url-shortening`: The `POST /Create-URL` handler must now compute and persist `expires_at` for every new record. The database schema (`urls` table) gains an `expires_at` column.

## Impact

- **Database schema**: `urls` table gains `expires_at TIMESTAMP WITH TIME ZONE NOT NULL`.
- **API surface**: New `GET /<code>` endpoint for redirection with expiration check.
- **Cache layer**: Redis SET operations on short codes must include `EXPIRE`/TTL.
- **Background jobs**: New cleanup worker (cron/loop) for periodic deletion of expired rows.
- **Configuration**: No new environment variables required; 60-day TTL is a system constant.
- **Tests**: New unit tests for expiration calculation, integration tests for 410 response and persistence.
