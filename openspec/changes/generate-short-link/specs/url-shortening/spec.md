## ADDED Requirements

### Requirement: Create short URL
The system SHALL accept a `POST` request at `/Create-URL` with a JSON body of the form `{"url": "<long-url>"}` and, when the URL is valid, respond with HTTP `201 Created` and a JSON body `{"short_url": "<public-base-url>/<code>"}` where `<code>` is the Base62-encoded Snowflake ID of the persisted record.

#### Scenario: Valid URL is shortened
- **WHEN** a client sends `POST /Create-URL` with body `{"url": "https://www.example.com/some/long/path"}` and the URL parses with an http or https scheme
- **THEN** the system responds with status `201` and a body `{"short_url": "https://<base>/<code>"}` where `<code>` matches `[A-Za-z0-9]+`

#### Scenario: Short URL points to a persisted record
- **WHEN** a valid request is processed
- **THEN** the system writes a row to the `urls` table containing the Snowflake ID, the original URL, and a `created_at` timestamp
- **AND** the response is sent only after the row is committed

#### Scenario: Short code is alphanumeric
- **WHEN** any request is processed successfully
- **THEN** the `<code>` segment of the returned `short_url` SHALL contain only characters in `[A-Za-z0-9]`
- **AND** the same Snowflake ID MUST always encode to the same code (encode/decode are exact inverses)

### Requirement: Validate request payload
The system SHALL reject malformed or oversized URL payloads with HTTP `400 Bad Request` and a JSON body `{"detail": "<message>"}` describing the failure. A payload is malformed if the body is not valid JSON, the `url` field is missing, the value is not a string, the value does not parse as an absolute URL with an http or https scheme, or the value exceeds 2048 characters.

#### Scenario: Missing url field
- **WHEN** a client sends `POST /Create-URL` with body `{}` or with no `url` key
- **THEN** the system responds with status `400` and a descriptive `detail`

#### Scenario: Non-string url value
- **WHEN** a client sends `POST /Create-URL` with body `{"url": 123}` or any non-string value
- **THEN** the system responds with status `400` and a descriptive `detail`

#### Scenario: URL without scheme
- **WHEN** a client sends `POST /Create-URL` with body `{"url": "example.com/path"}` (no `http://` or `https://`)
- **THEN** the system responds with status `400` and a descriptive `detail`

#### Scenario: URL exceeds 2048 characters
- **WHEN** a client sends a `url` value whose length is greater than 2048 characters
- **THEN** the system responds with status `400` and a descriptive `detail` mentioning the length limit

### Requirement: Guarantee unique Snowflake IDs
The Snowflake ID generator SHALL produce a unique 64-bit positive integer for every call within a single process lifetime, under normal monotonic-clock conditions.

#### Scenario: No duplicates in 10,000 calls
- **WHEN** the generator is called 10,000 times in a tight loop
- **THEN** every returned ID is distinct

#### Scenario: Sequence exhaustion within one millisecond
- **WHEN** the generator is called more than 4096 times within a single millisecond
- **THEN** the generator blocks (does not return) until the next millisecond before issuing further IDs
- **AND** every ID issued across the boundary remains unique

### Requirement: Detect clock drift
The Snowflake ID generator SHALL raise an `InvalidSystemClock` error if the system clock moves backwards relative to the last issued timestamp. The generator MUST NOT issue a duplicate or past-timestamped ID in that case.

#### Scenario: Clock moves backwards
- **WHEN** the generator has issued at least one ID with timestamp `T`
- **AND** the next observed wall-clock millisecond is `T' < T`
- **THEN** the next call to the generator raises `InvalidSystemClock`

### Requirement: Fail closed on persistence errors
The system SHALL respond with HTTP `500 Internal Server Error` and MUST NOT return a short URL when the database insert fails for any reason (connection loss, constraint violation, timeout).

#### Scenario: Database write fails
- **WHEN** the database insert for a validated request raises any exception
- **THEN** the system responds with status `500` and a body `{"detail": "..."}` 
- **AND** no `short_url` is returned to the client

### Requirement: Configure base URL and node ID from environment
The system SHALL read `SHORT_BASE_URL` (used to build the returned `short_url`) and `SNOWFLAKE_NODE_ID` (an integer in `[0, 1023]` used as the worker bits of the Snowflake ID) from environment variables at startup. The service MUST fail to start if `SNOWFLAKE_NODE_ID` is set to a value outside `[0, 1023]`.

#### Scenario: Missing or invalid node ID
- **WHEN** `SNOWFLAKE_NODE_ID` is unset (defaults to `0`), non-integer, or outside `[0, 1023]`
- **THEN** the service either uses the default or refuses to start with a clear error
