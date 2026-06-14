## ADDED Requirements

### Requirement: Calculate expiration date at creation
The system SHALL set `expires_at` for every new URL record to exactly `created_at + 60 days`, expressed in UTC. The calculation SHALL use a timedelta of 5,184,000 seconds (60 × 24 × 3600), not calendar-month arithmetic.

#### Scenario: Expiration is exactly 60 days after creation
- **WHEN** a new short URL is created at timestamp `T` (UTC)
- **THEN** the persisted `expires_at` SHALL equal `T + 5,184,000 seconds`

#### Scenario: Calculation handles leap years
- **WHEN** creation occurs on `2024-02-28T12:00:00Z` (a leap year)
- **THEN** `expires_at` SHALL be `2024-04-28T12:00:00Z` (exactly 60 × 86400 seconds later)

### Requirement: Cache entries carry native TTL
The system SHALL set a Redis key-level TTL on every short code cache entry equal to the remaining seconds until `expires_at`, ensuring automatic Redis eviction when the URL expires.

#### Scenario: Cache TTL matches remaining lifetime
- **WHEN** a short URL is created with `expires_at = now + 60 days`
- **AND** the code-to-URL mapping is written to Redis
- **THEN** the Redis key SHALL have a TTL of 5,184,000 seconds (60 days)

#### Scenario: Cache TTL on miss rehydration
- **WHEN** a cache miss occurs and the record is fetched from the database with `expires_at` still in the future
- **THEN** the rehydrated cache key SHALL have a TTL equal to `expires_at - now(UTC)` in seconds, with a minimum of 1 second

### Requirement: Background cleanup of expired database records
The system SHALL run a periodic background task that deletes rows from the `urls` table where `expires_at <= now(UTC)`.

#### Scenario: Worker deletes expired rows
- **WHEN** the cleanup worker executes a purge cycle
- **AND** there are rows in the `urls` table with `expires_at <= now(UTC)`
- **THEN** those rows are deleted from the database
- **AND** rows with `expires_at > now(UTC)` are not affected

#### Scenario: Worker handles empty result sets
- **WHEN** the cleanup worker executes a purge cycle
- **AND** no rows have `expires_at <= now(UTC)`
- **THEN** the worker completes without error and no rows are deleted

### Requirement: Expired shortcode reuse on creation
The system SHALL treat an existing database row with `expires_at <= now(UTC)` as available when a newly generated short code collides with it, allowing the new URL to reuse the code.

#### Scenario: Collision with expired record
- **WHEN** the short code generator produces a code that matches an existing row in `urls`
- **AND** the existing row has `expires_at <= now(UTC)`
- **THEN** the system deletes the expired row and inserts the new record with the same code
- **AND** the response returns the new short URL successfully (201 Created)
