## ADDED Requirements

### Requirement: Admin identification via environment variable
The system SHALL identify administrators from the `ADMIN_EMAILS` environment variable, a comma-separated list of email addresses. At startup, the system SHALL parse this list into a set. If the variable is empty or unset, no users are administrators.

#### Scenario: Admin email matches
- **WHEN** `ADMIN_EMAILS=admin@empresa.com,jefe@empresa.com`
- **AND** a request arrives with `X-Authenticated-User: admin@empresa.com`
- **THEN** the user is recognized as an administrator

#### Scenario: Non-admin email does not match
- **WHEN** `ADMIN_EMAILS=admin@empresa.com`
- **AND** a request arrives with `X-Authenticated-User: user@empresa.com`
- **THEN** the user is NOT recognized as an administrator
- **AND** admin-protected endpoints return 403

### Requirement: Admin can block a URL
The system SHALL accept a `POST` request at `/admin/block/{short_code}` from an authenticated administrator and set `is_blocked = true` on the corresponding row. The system SHALL evict any cached entry for that URL from Redis.

#### Scenario: Admin blocks a valid URL
- **WHEN** an admin sends `POST /admin/block/{short_code}` for an existing URL
- **THEN** the system responds with status `200` and `{"status": "blocked"}`
- **AND** the `is_blocked` column is set to `true`
- **AND** the Redis cache entry for the Snowflake ID is deleted
- **AND** subsequent `GET /{short_code}` returns 403

#### Scenario: Blocking an already-blocked URL is idempotent
- **WHEN** an admin blocks a URL that already has `is_blocked = true`
- **THEN** the system responds with status `200` and `{"status": "blocked"}`
- **AND** no error occurs

#### Scenario: Blocking a non-existent URL returns 404
- **WHEN** an admin sends `POST /admin/block/{short_code}` for a non-existent URL
- **THEN** the system responds with status `404`

#### Scenario: Non-admin cannot block
- **WHEN** an authenticated non-admin user sends `POST /admin/block/{short_code}`
- **THEN** the system responds with status `403`

### Requirement: Admin can unblock a URL
The system SHALL accept a `POST` request at `/admin/unblock/{short_code}` from an authenticated administrator and set `is_blocked = false` on the corresponding row. The system SHALL evict any cached BLOCKED sentinel for that URL from Redis.

#### Scenario: Admin unblocks a blocked URL
- **WHEN** an admin sends `POST /admin/unblock/{short_code}` for a blocked URL
- **THEN** the system responds with status `200` and `{"status": "unblocked"}`
- **AND** `is_blocked` is set to `false`
- **AND** the Redis cache entry for the Snowflake ID is deleted
- **AND** subsequent `GET /{short_code}` returns 302

#### Scenario: Unblocking an already-unblocked URL is idempotent
- **WHEN** an admin unblocks a URL that already has `is_blocked = false`
- **THEN** the system responds with status `200` and `{"status": "unblocked"}`
- **AND** no error occurs

#### Scenario: Non-admin cannot unblock
- **WHEN** an authenticated non-admin user sends `POST /admin/unblock/{short_code}`
- **THEN** the system responds with status `403`

### Requirement: Admin can list all URLs
The system SHALL accept a `GET` request at `/admin/urls` from an authenticated administrator and return a paginated list of ALL URLs in the system, ordered by creation time descending, including the `created_by` field. Pagination SHALL use the same cursor-based mechanism as `GET /my-urls`.

#### Scenario: Admin lists all URLs
- **WHEN** an admin sends `GET /admin/urls`
- **AND** URLs from multiple users exist
- **THEN** the system responds with status `200`
- **AND** the response includes URLs from all users
- **AND** each item includes `created_by` identifying the owner

#### Scenario: Non-admin cannot list all URLs
- **WHEN** a non-admin sends `GET /admin/urls`
- **THEN** the system responds with status `403`

#### Scenario: Admin list supports pagination
- **WHEN** an admin sends `GET /admin/urls?cursor=<id>&limit=20`
- **THEN** the response follows the same cursor-pagination contract as `/my-urls`
