## ADDED Requirements

### Requirement: Click counter on successful redirect
The system SHALL increment a per-URL click counter atomically every time a `GET /{short_code}` request resolves to a valid, non-blocked, non-expired, non-deleted URL and returns HTTP 302. The counter SHALL NOT increment for 403 (blocked), 404 (not found), 410 (expired/deleted), or 400 (invalid code) responses.

#### Scenario: Click increments on valid redirect
- **WHEN** a client sends `GET /{short_code}` and the URL is valid
- **AND** the system responds with 302
- **THEN** the `clicks` column for that URL is incremented by 1

#### Scenario: Click does NOT increment on blocked URL
- **WHEN** a client sends `GET /{short_code}` and the URL is blocked
- **AND** the system responds with 403
- **THEN** the `clicks` column is NOT modified

#### Scenario: Click does NOT increment on expired URL
- **WHEN** a client sends `GET /{short_code}` and the URL is expired
- **AND** the system responds with 410
- **THEN** the `clicks` column is NOT modified

#### Scenario: Concurrent clicks are counted correctly
- **WHEN** multiple clients simultaneously request the same valid short code
- **THEN** the `clicks` counter reflects the total number of successful redirects
- **AND** no clicks are lost due to race conditions

### Requirement: Click count visible in user URL views
The system SHALL include the `clicks` field in the JSON response of `GET /my-urls` (list) and `GET /my-urls/{short_code}` (detail). The value SHALL be a non-negative integer.

#### Scenario: Click count appears in list
- **WHEN** an authenticated user sends `GET /my-urls`
- **AND** one of their URLs has been clicked 5 times
- **THEN** that item in the `urls` array includes `"clicks": 5`

#### Scenario: Click count appears in detail
- **WHEN** an authenticated user sends `GET /my-urls/{short_code}`
- **AND** the URL has been clicked 3 times
- **THEN** the response includes `"clicks": 3`

### Requirement: Click count visible in admin URL list
The system SHALL include the `clicks` field in the JSON response of `GET /admin/urls`.

#### Scenario: Admin sees click counts for all URLs
- **WHEN** an admin sends `GET /admin/urls`
- **THEN** each item includes the `clicks` field

### Requirement: Admin can view any URL's click stats
The system SHALL accept a `GET` request at `/admin/stats/{short_code}` from an authenticated administrator and return the URL's metadata including click count, regardless of who owns the URL.

#### Scenario: Admin views stats for any URL
- **WHEN** an admin sends `GET /admin/stats/{short_code}` for any existing URL
- **THEN** the system responds with status `200` and includes the `clicks` field

#### Scenario: Non-admin cannot view admin stats
- **WHEN** a non-admin authenticated user sends `GET /admin/stats/{short_code}`
- **THEN** the system responds with status `403`

### Requirement: Click increment failure does not block redirect
The system SHALL complete the redirect even if the click counter increment fails. A warning SHALL be logged.

#### Scenario: Redirect succeeds despite counter failure
- **WHEN** a client requests a valid short code
- **AND** the database increment operation fails
- **THEN** the system still responds with 302
- **AND** a warning is logged
