## ADDED Requirements

### Requirement: Rate limit check before URL creation
The system SHALL enforce rate limiting on `POST /Create-URL` requests by authenticated user before processing the request. When the rate limit is exceeded, the system SHALL respond with HTTP `429 Too Many Requests` and SHALL NOT execute the URL creation handler or write to the database.

#### Scenario: Rate limit passes, creation proceeds normally
- **WHEN** a client sends `POST /Create-URL` with valid authentication and a valid URL payload
- **AND** the authenticated user is within their creation rate limit
- **THEN** the system creates the short URL and responds with status `201` as specified

#### Scenario: Rate limit exceeded, creation blocked
- **WHEN** a client sends `POST /Create-URL` with valid authentication
- **AND** the authenticated user has exceeded their creation rate limit
- **THEN** the system responds with status `429`
- **AND** the URL creation handler is NOT invoked
- **AND** no row is written to the `urls` table
- **AND** the `Retry-After` header is present
