# url-redirect Specification

## Purpose
TBD - created by archiving change redirect-short-url. Update Purpose after archive.
## Requirements
### Requirement: Resolve valid short code
The system SHALL accept a `GET` request at `/{short_code}` where `short_code` consists only of characters in `[0-9A-Za-z]` and corresponds to a stored, non-blocked URL. The system SHALL respond with HTTP `302 Found` and a `Location` header pointing to the original URL.

#### Scenario: Valid short code redirects
- **WHEN** a client sends `GET /aB3x9Q` and `aB3x9Q` decodes to a Snowflake ID that exists in the database and `is_blocked` is `False`
- **THEN** the system responds with status `302` and the `Location` header contains the original URL associated with that ID

#### Scenario: Short code resolved via cache
- **WHEN** a client sends `GET /aB3x9Q` and the Snowflake ID is present in the Redis cache with a positive record
- **THEN** the system responds with status `302` and the `Location` header is served from the cache without querying the database

#### Scenario: Cache miss populates cache
- **WHEN** a client sends `GET /aB3x9Q` and the ID is not in Redis but exists in the database
- **THEN** the system stores the resolved URL in Redis with a TTL of at least 300 seconds
- **AND** responds with status `302`

### Requirement: Reject invalid short code format
The system SHALL reject short codes that contain characters outside the Base62 alphabet with HTTP `400 Bad Request` and a descriptive error message.

#### Scenario: Invalid characters in short code
- **WHEN** a client sends `GET /aB3x9Q-` or any code containing characters not in `[0-9A-Za-z]`
- **THEN** the system responds with status `400` and a body `{"detail": "..."}` describing the format error

### Requirement: Handle non-existent short code
The system SHALL respond with HTTP `404 Not Found` when the short code decodes to a Snowflake ID that does not exist in the database.

#### Scenario: Non-existent ID returns 404
- **WHEN** a client sends `GET /NonExistent1` and the decoded ID has no matching row in the `urls` table
- **THEN** the system responds with status `404` with a descriptive body

#### Scenario: Negative cache prevents DB query on repeat
- **WHEN** a client sends `GET /NonExistent1` and the ID is not found in the database
- **THEN** the system stores a negative cache entry in Redis with a limited TTL (≤ 60 seconds)
- **AND** subsequent requests for the same ID within the TTL return `404` without querying the database

### Requirement: Block malicious URLs
The system SHALL respond with HTTP `403 Forbidden` when the short code resolves to a URL whose `is_blocked` flag is `True`. The original URL MUST NOT be disclosed in the response.

#### Scenario: Blocked URL returns 403
- **WHEN** a client sends `GET /BlockedCode1` and the decoded Snowflake ID exists in the database with `is_blocked = True`
- **THEN** the system responds with status `403` and a descriptive body
- **AND** the `Location` header is not set

### Requirement: Gracefully degrade when cache is unavailable
The system SHALL continue to resolve short codes when Redis is unreachable by falling back to direct database reads. The redirect response MUST be identical (same status, same headers) whether the cache is available or not.

#### Scenario: Redis connection failure falls through to DB
- **WHEN** a client sends `GET /aB3x9Q` and the Redis server is unreachable or raises a connection error
- **THEN** the system queries the database directly
- **AND** responds with the same status as if the cache were available (302 for valid, 404 for missing, 403 for blocked)

### Requirement: Cache blocked and non-existent records
The system SHALL cache the blocked status and the non-existent status in Redis with a moderate TTL (≤ 300 seconds for blocked, ≤ 60 seconds for non-existent) so that repeated requests do not hit the database.

#### Scenario: Cached blocked status prevents DB query
- **WHEN** a client sends `GET /BlockedCode1` and the blocked status was cached from a previous query
- **THEN** the system responds with `403` without querying the database

#### Scenario: Cached negative status expires after TTL
- **WHEN** a client sends `GET /NonExistent1` and the negative cache entry has expired
- **THEN** the system queries the database again to check if the ID has been created since the last request

### Requirement: Return 410 Gone for soft-deleted URLs
The system SHALL respond with HTTP `410 Gone` when a `GET /{short_code}` request resolves a short code whose corresponding row in the `urls` table has a non-NULL `deleted_at` value. The response body SHALL be a JSON object `{"detail": "..."}` with a generic gone message that does not distinguish "deleted" from "expired".

#### Scenario: Soft-deleted URL returns 410
- **WHEN** a client sends `GET /{short_code}` and the corresponding row has `deleted_at IS NOT NULL` regardless of `expires_at` or `is_blocked`
- **THEN** the system responds with status `410` and a body `{"detail": "..."}` indicating the short link is gone
- **AND** the `Location` header is not set

#### Scenario: Soft-deleted URL caches a deleted sentinel
- **WHEN** the system resolves a soft-deleted URL from the database (cache miss) and writes the resolution to the cache
- **THEN** the cache entry SHALL be a `DELETED` sentinel with a TTL of no more than 300 seconds
- **AND** subsequent requests within that TTL respond with `410` without querying the database

#### Scenario: Cache is not poisoned by a fresh soft delete
- **WHEN** an authenticated user soft-deletes a URL and the URL was previously cached as a positive record
- **THEN** the positive cache entry is removed by the delete operation
- **AND** the next `GET /{short_code}` does not serve a stale `302` redirect from cache

