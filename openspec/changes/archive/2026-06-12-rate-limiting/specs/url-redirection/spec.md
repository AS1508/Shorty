## ADDED Requirements

### Requirement: Rate limit check before URL resolution
The system SHALL enforce rate limiting on `GET /{short_code}` requests by client IP before processing the request. When the rate limit is exceeded, the system SHALL respond with HTTP `429 Too Many Requests` and SHALL NOT execute the URL resolution handler, query the database, or access the cache.

#### Scenario: Rate limit passes, resolution proceeds normally
- **WHEN** a client sends `GET /{short_code}` with a valid short code
- **AND** the client IP is within the redirection rate limit
- **THEN** the system resolves the short code and responds with the appropriate status (`302`, `404`, `410`, or `403`) as specified

#### Scenario: Rate limit exceeded, resolution blocked
- **WHEN** a client sends `GET /{short_code}`
- **AND** the client IP has exceeded the redirection rate limit
- **THEN** the system responds with status `429`
- **AND** the URL resolution handler is NOT invoked
- **AND** no database query or cache access is performed for this request
- **AND** the `Retry-After` header is present
