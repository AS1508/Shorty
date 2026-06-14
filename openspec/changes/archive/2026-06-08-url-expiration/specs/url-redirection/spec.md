## ADDED Requirements

### Requirement: Resolve short code and redirect
The system SHALL accept a `GET` request at `/<code>` and, when the short code maps to a non-expired URL record, respond with HTTP `302 Found` and a `Location` header set to the original URL.

#### Scenario: Valid short code redirects
- **WHEN** a client sends `GET /<code>` for a short code that exists in the database and has `expires_at > now(UTC)`
- **THEN** the system responds with status `302` and a `Location` header containing the original URL

#### Scenario: Short code is cached in Redis
- **WHEN** a client sends `GET /<code>` and the `(code -> original_url)` mapping exists in Redis with a valid TTL
- **THEN** the system responds with status `302` and a `Location` header containing the cached original URL
- **AND** the system does not query the database for this request

#### Scenario: Short code not in cache but in database
- **WHEN** a client sends `GET /<code>` that is NOT in Redis but IS in the `urls` table with `expires_at > now(UTC)`
- **THEN** the system queries the database, finds the record, responds with status `302`
- **AND** the system populates the Redis cache with the code-to-URL mapping and a TTL matching the remaining time until expiration

### Requirement: Return 410 Gone for expired URLs
The system SHALL respond with HTTP `410 Gone` when a `GET /<code>` request resolves a short code whose `expires_at` timestamp is less than or equal to the current UTC time.

#### Scenario: Expired URL returns 410
- **WHEN** a client sends `GET /<code>` for a short code that exists in the database but has `expires_at <= now(UTC)`
- **THEN** the system responds with status `410` and a JSON body `{"detail": "This short link has expired"}`

#### Scenario: Expired URL not in cache
- **WHEN** a client sends `GET /<code>` for an expired short code
- **AND** the Redis key has already been evicted by TTL
- **THEN** the system queries the database, finds the expired record, and responds with status `410`

### Requirement: Return 404 for unknown short codes
The system SHALL respond with HTTP `404 Not Found` when a `GET /<code>` request specifies a short code that does not match any row in the `urls` table.

#### Scenario: Unknown short code
- **WHEN** a client sends `GET /<code>` for a code that does not exist in the database
- **THEN** the system responds with status `404` and a JSON body `{"detail": "Short link not found"}`

### Requirement: Short code format validation
The system SHALL reject `GET` requests with a malformed short code (not matching `[A-Za-z0-9]+`) with HTTP `400 Bad Request`.

#### Scenario: Code contains invalid characters
- **WHEN** a client sends `GET /<code>` where `<code>` contains characters outside `[A-Za-z0-9]`
- **THEN** the system responds with status `400` and a JSON body `{"detail": "..."}` describing the format error
