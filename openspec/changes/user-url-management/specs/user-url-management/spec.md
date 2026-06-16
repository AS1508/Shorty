## ADDED Requirements

### Requirement: Authenticated user can list own URLs

The system SHALL accept a `GET` request at `/my-urls` from an authenticated user (identified by the `X-Authenticated-User` header) and return a JSON body containing a paginated list of URLs owned by that user, ordered by creation time descending (newest first). Pagination SHALL be cursor-based using the `cursor` and `limit` query parameters.

#### Scenario: Empty list when user has no URLs
- **WHEN** an authenticated client sends `GET /my-urls`
- **AND** the user has no URLs in the `urls` table with `created_by` matching their email
- **THEN** the system responds with status `200` and a body `{"urls": [], "has_more": false}`

#### Scenario: List returns user's own URLs
- **WHEN** an authenticated client sends `GET /my-urls`
- **AND** the user has created `N` URLs
- **THEN** the system responds with status `200`
- **AND** the `urls` array contains at most `limit` items (default 20, max 100)
- **AND** each item contains `short_code`, `short_url`, `original_url`, `created_at`, `expires_at`, `is_expired`, `is_blocked`, and `deleted_at`
- **AND** items are ordered by creation time descending (newest first)

#### Scenario: Pagination via cursor and limit
- **WHEN** an authenticated client sends `GET /my-urls?cursor=<id>&limit=10`
- **AND** there are more URLs beyond the cursor position
- **THEN** the system responds with status `200`
- **AND** `urls` contains at most 10 items with `id < cursor`
- **AND** `next_cursor` is set to the last item's `id`
- **AND** `has_more` is `true` if there are further items beyond this page

#### Scenario: Last page has no cursor
- **WHEN** an authenticated client sends `GET /my-urls` and receives the last page of results
- **THEN** `has_more` is `false`
- **AND** `next_cursor` is absent from the response

#### Scenario: Limit is clamped to valid range
- **WHEN** an authenticated client sends `GET /my-urls?limit=0` or `GET /my-urls?limit=200`
- **THEN** the system clamps `limit` to 1 and 100 respectively
- **AND** responds with a valid paginated response

#### Scenario: Invalid cursor value
- **WHEN** an authenticated client sends `GET /my-urls?cursor=abc`
- **THEN** the system responds with status `400` and a body `{"detail": "..."}` describing that cursor must be a positive integer

#### Scenario: List includes expired and deleted URLs
- **WHEN** an authenticated client sends `GET /my-urls`
- **AND** some of the user's URLs are expired (`expires_at <= now()`) or soft-deleted (`deleted_at IS NOT NULL`)
- **THEN** those URLs appear in the list
- **AND** expired URLs have `is_expired: true`
- **AND** soft-deleted URLs have a non-null `deleted_at`

#### Scenario: List only shows own URLs
- **WHEN** user A and user B each have URLs in the database
- **AND** user A sends `GET /my-urls`
- **THEN** the response only contains URLs where `created_by` matches user A's email

#### Scenario: Unauthenticated request is rejected
- **WHEN** a client sends `GET /my-urls` without the `X-Authenticated-User` header
- **THEN** the system responds with status `403`

### Requirement: Authenticated user can view own URL details

The system SHALL accept a `GET` request at `/my-urls/{short_code}` from an authenticated user and, when the short code decodes to a stored URL whose `created_by` matches the authenticated user's email, respond with HTTP `200 OK` and a JSON body containing `short_code`, `short_url`, `original_url`, `created_at`, `expires_at`, `is_expired`, `is_blocked`, and `deleted_at`.

#### Scenario: User views own URL
- **WHEN** an authenticated client sends `GET /my-urls/{short_code}`
- **AND** the decoded ID corresponds to a row in the `urls` table with `created_by` equal to the authenticated email
- **THEN** the system responds with status `200`
- **AND** the body contains all metadata fields for that URL

#### Scenario: User cannot view another user's URL
- **WHEN** an authenticated client sends `GET /my-urls/{short_code}`
- **AND** the row's `created_by` does not match the authenticated email
- **THEN** the system responds with status `404`

#### Scenario: Non-existent short code returns 404
- **WHEN** an authenticated client sends `GET /my-urls/{short_code}`
- **AND** the decoded ID does not exist in the database
- **THEN** the system responds with status `404`

#### Scenario: Invalid short code format is rejected
- **WHEN** an authenticated client sends `GET /my-urls/{short_code}`
- **AND** `{short_code}` contains characters outside `[A-Za-z0-9]`
- **THEN** the system responds with status `400` and a body `{"detail": "..."}` describing the format error
- **AND** the database is not queried

#### Scenario: Expired URL shows is_expired flag
- **WHEN** an authenticated client sends `GET /my-urls/{short_code}`
- **AND** the URL's `expires_at` is in the past
- **THEN** the system responds with status `200`
- **AND** `is_expired` is `true`

#### Scenario: Blocked URL shows is_blocked flag
- **WHEN** an authenticated client sends `GET /my-urls/{short_code}`
- **AND** `is_blocked` is `true`
- **THEN** the system responds with status `200`
- **AND** `is_blocked` is `true`

#### Scenario: Deleted URL shows deleted_at timestamp
- **WHEN** an authenticated client sends `GET /my-urls/{short_code}`
- **AND** `deleted_at` is not null
- **THEN** the system responds with status `200`
- **AND** `deleted_at` contains the UTC timestamp of deletion
