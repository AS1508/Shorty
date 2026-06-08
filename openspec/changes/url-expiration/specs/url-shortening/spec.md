## MODIFIED Requirements

### Requirement: Create short URL
The system SHALL accept a `POST` request at `/Create-URL` with a JSON body of the form `{"url": "<long-url>"}` and valid authentication headers (`X-Authenticated-User` with a matching `X-Auth-Signature` HMAC), and, when the URL is valid, respond with HTTP `201 Created` and a JSON body `{"short_url": "<public-base-url>/<code>"}` where `<code>` is the Base62-encoded Snowflake ID of the persisted record. The authenticated user's email SHALL be persisted in the `created_by` column, the creation timestamp in `created_at`, and the expiration timestamp in `expires_at` (set to `created_at + 60 days` in UTC) of the `urls` table.

#### Scenario: Valid URL is shortened by authenticated user
- **WHEN** a client sends `POST /Create-URL` with body `{"url": "https://www.example.com/some/long/path"}` and valid `X-Authenticated-User` + `X-Auth-Signature` headers
- **AND** the URL parses with an http or https scheme
- **THEN** the system responds with status `201` and a body `{"short_url": "https://<base>/<code>"}` where `<code>` matches `[A-Za-z0-9]+`

#### Scenario: Short URL points to a persisted record
- **WHEN** a valid authenticated request is processed
- **THEN** the system writes a row to the `urls` table containing the Snowflake ID, the original URL, a `created_at` timestamp, an `expires_at` timestamp exactly 60 days after `created_at`, and the email from the `X-Authenticated-User` header in `created_by`
- **AND** the response is sent only after the row is committed

#### Scenario: Unauthenticated creation is rejected
- **WHEN** a client sends `POST /Create-URL` without the `X-Authenticated-User` header
- **THEN** the system responds with status `403` and a body `{"detail": "Forbidden"}`
- **AND** no row is written to the `urls` table

#### Scenario: Creation with invalid signature is rejected
- **WHEN** a client sends `POST /Create-URL` with a valid `X-Authenticated-User` header but an invalid `X-Auth-Signature`
- **AND** `PROXY_SHARED_SECRET` is set
- **THEN** the system responds with status `403` and a body `{"detail": "Forbidden"}`
- **AND** no row is written to the `urls` table

#### Scenario: Short code is alphanumeric
- **WHEN** any request is processed successfully
- **THEN** the `<code>` segment of the returned `short_url` SHALL contain only characters in `[A-Za-z0-9]`
- **AND** the same Snowflake ID MUST always encode to the same code (encode/decode are exact inverses)

