# rate-limiting Specification

## Purpose
Rate limiting de dos capas sobre Redis para proteger los endpoints de Shorty: creación de URLs por usuario autenticado y redirección por IP. Usa ventana fija con fail-open.

## ADDED Requirements

### Requirement: Rate limit URL creation by authenticated user
The system SHALL limit the number of `POST /Create-URL` requests per authenticated user within a configurable time window using a fixed-window counter in Redis. When the limit is exceeded, the system SHALL respond with HTTP `429 Too Many Requests` and a `Retry-After` header. The counter SHALL be keyed by the user's email (from the `X-Authenticated-User` header) and the current window timestamp.

#### Scenario: User creates URLs within the limit
- **WHEN** an authenticated user sends `POST /Create-URL` and their creation count in the current window is below the configured limit
- **THEN** the rate limiter allows the request to proceed to the handler
- **AND** the Redis counter for that user+window is incremented by 1

#### Scenario: User exceeds the creation limit
- **WHEN** an authenticated user sends `POST /Create-URL` and their creation count in the current window equals or exceeds the configured limit
- **THEN** the system responds with status `429`
- **AND** the body contains `{"detail": "Rate limit exceeded. Try again in <n> seconds."}`
- **AND** the `Retry-After` header is set to the number of seconds remaining in the current window
- **AND** the request handler is NOT invoked
- **AND** no row is written to the `urls` table

#### Scenario: Window boundary resets the counter
- **WHEN** the current time window expires
- **AND** an authenticated user sends `POST /Create-URL`
- **THEN** a new Redis counter is created for the new window
- **AND** the request is allowed if the new counter is below the limit

### Requirement: Rate limit URL redirection by client IP
The system SHALL limit the number of `GET /{short_code}` requests per client IP address within a configurable time window using a fixed-window counter in Redis. When the limit is exceeded, the system SHALL respond with HTTP `429 Too Many Requests` and a `Retry-After` header. The counter SHALL be keyed by the client's IP address and the current window timestamp.

#### Scenario: Client resolves URLs within the limit
- **WHEN** a client sends `GET /{short_code}` and their IP's request count in the current window is below the configured limit
- **THEN** the rate limiter allows the request to proceed to the handler
- **AND** the Redis counter for that IP+window is incremented by 1

#### Scenario: Client exceeds the redirection limit
- **WHEN** a client sends `GET /{short_code}` and their IP's request count in the current window equals or exceeds the configured limit
- **THEN** the system responds with status `429`
- **AND** the body contains `{"detail": "Rate limit exceeded. Try again in <n> seconds."}`
- **AND** the `Retry-After` header is set to the number of seconds remaining in the current window
- **AND** the request handler is NOT invoked
- **AND** no database or cache lookup is performed for this request

#### Scenario: Different IPs have independent counters
- **WHEN** client A from IP `203.0.113.1` and client B from IP `203.0.113.2` both send `GET /{short_code}`
- **THEN** their respective counters in Redis are independent
- **AND** client A exhausting their limit does not affect client B

### Requirement: Fail-open on Redis unavailability
The system SHALL allow requests to proceed without rate limiting when Redis is unreachable or raises an error during rate limit check operations.

#### Scenario: Redis connection refused during rate limit check
- **WHEN** a rate limit check attempts to increment a Redis counter
- **AND** Redis raises a `ConnectionError` or timeout
- **THEN** the system logs a warning indicating rate limiting is skipped
- **AND** the request proceeds to the handler as if the check passed
- **AND** no `429` response is generated due to the Redis failure

#### Scenario: Redis recovers after failure
- **WHEN** Redis becomes reachable again after a period of unavailability
- **THEN** subsequent requests have rate limiting applied normally
- **AND** counters start from zero for the current windows

### Requirement: Standard 429 response format
The system SHALL respond to rate-limited requests with a consistent HTTP `429 Too Many Requests` response including a JSON body and a `Retry-After` header.

#### Scenario: Rate-limited creation returns 429
- **WHEN** an authenticated user exceeds the creation rate limit
- **THEN** the response has status `429`
- **AND** `Content-Type` is `application/json`
- **AND** the body is `{"detail": "Rate limit exceeded. Try again in <n> seconds."}`
- **AND** the `Retry-After` header contains the integer number of seconds remaining in the current window
- **AND** `<n>` in the detail string matches the `Retry-After` value

#### Scenario: Rate-limited redirection returns 429
- **WHEN** a client exceeds the redirection rate limit
- **THEN** the response has status `429` with the same format as creation rate limiting
- **AND** the handler is not invoked (no 302, 404, 410, or 403 is possible)

### Requirement: Extract real client IP behind proxy
The system SHALL extract the real client IP address from the `X-Forwarded-For` header when present, using the rightmost entry (the one added by the trusted proxy). When the header is absent, the system SHALL fall back to the direct connection IP from `request.client.host`.

#### Scenario: Single proxy forwards request
- **WHEN** a request arrives with `X-Forwarded-For: 203.0.113.5`
- **THEN** the rate limiter uses `203.0.113.5` as the client IP

#### Scenario: Multiple proxies in chain
- **WHEN** a request arrives with `X-Forwarded-For: 10.0.0.1, 203.0.113.5`
- **THEN** the rate limiter uses `203.0.113.5` (rightmost entry) as the client IP

#### Scenario: No proxy header present
- **WHEN** a request arrives without an `X-Forwarded-For` header
- **THEN** the rate limiter uses the value of `request.client.host` as the client IP

### Requirement: Configurable rate limits via environment
The system SHALL read rate limit parameters from environment variables at startup, falling back to default values when variables are unset.

#### Scenario: Custom rate limits configured
- **WHEN** `RATE_LIMIT_CREATE_COUNT=30` and `RATE_LIMIT_CREATE_WINDOW_SECONDS=1800` are set
- **THEN** the creation rate limiter allows up to 30 URLs per 1800-second window per user

#### Scenario: Default values when not configured
- **WHEN** `RATE_LIMIT_CREATE_COUNT` is not set
- **THEN** the creation rate limiter uses the default of 20 URLs per hour (3600 seconds)

#### Scenario: Redirect rate limits configured independently
- **WHEN** `RATE_LIMIT_REDIRECT_COUNT=200` and `RATE_LIMIT_REDIRECT_WINDOW_SECONDS=120` are set
- **THEN** the redirection rate limiter allows up to 200 requests per 120-second window per IP
