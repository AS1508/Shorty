## ADDED Requirements

### Requirement: Verify proxy signature for authenticated endpoints
The system SHALL verify that the `X-Authenticated-User` header was cryptographically signed by a trusted proxy. The verification SHALL use HMAC-SHA256 over the email value with a shared secret (`PROXY_SHARED_SECRET`), comparing against the `X-Auth-Signature` header (base64-encoded). The comparison SHALL use a constant-time algorithm. If verification fails — including missing signature header, invalid base64, or non-matching HMAC — the system SHALL respond with HTTP `403 Forbidden`.

#### Scenario: HMAC verification succeeds
- **WHEN** a client sends a request to a protected endpoint with `X-Authenticated-User: dev@midominio.com` and a valid `X-Auth-Signature` header whose value matches `base64(HMAC-SHA256(secret, "dev@midominio.com"))`
- **THEN** the dependency extracts the email `dev@midominio.com` and passes it to the route handler

#### Scenario: Missing signature header
- **WHEN** a client sends a request with a valid `X-Authenticated-User` but no `X-Auth-Signature` header
- **AND** `PROXY_SHARED_SECRET` is set (production mode)
- **THEN** the system responds with status `403` and a body `{"detail": "Forbidden"}`

#### Scenario: Invalid signature
- **WHEN** a client sends a request with `X-Authenticated-User: dev@midominio.com` and `X-Auth-Signature` that does not match the computed HMAC
- **THEN** the system responds with status `403` and a body `{"detail": "Forbidden"}`

### Requirement: Require authentication header for protected endpoints
The system SHALL reject requests to protected endpoints that lack a valid `X-Authenticated-User` header. If the header is absent, empty, or does not contain the `@` character, the system SHALL respond with HTTP `403 Forbidden`.

#### Scenario: No authentication header
- **WHEN** a client sends a request to a protected endpoint without the `X-Authenticated-User` header
- **THEN** the system responds with status `403` and a body `{"detail": "Forbidden"}`

#### Scenario: Empty authentication header
- **WHEN** a client sends a request to a protected endpoint with `X-Authenticated-User: ""`
- **THEN** the system responds with status `403` and a body `{"detail": "Forbidden"}`

#### Scenario: Invalid email format
- **WHEN** a client sends a request to a protected endpoint with `X-Authenticated-User: not-an-email`
- **THEN** the system responds with status `403` and a body `{"detail": "Forbidden"}`

### Requirement: Public endpoints are not affected
The system SHALL NOT require authentication headers or signatures on endpoints designated as public. The `GET /{short_code}` redirect endpoint SHALL remain accessible to anonymous clients.

#### Scenario: Anonymous redirect still works
- **WHEN** a client sends `GET /{short_code}` without `X-Authenticated-User` or `X-Auth-Signature` headers for a valid short code
- **THEN** the system responds with status `302` and a `Location` header pointing to the original URL

### Requirement: Shared secret configuration
The system SHALL read a `PROXY_SHARED_SECRET` environment variable at startup. When the secret is set (non-empty), HMAC verification of the `X-Auth-Signature` header SHALL be enforced on all protected endpoints. When the secret is empty (e.g., local development), HMAC verification SHALL be skipped and the `X-Authenticated-User` header alone suffices.

#### Scenario: Dev mode skips HMAC
- **WHEN** `PROXY_SHARED_SECRET` is unset or empty
- **THEN** protected endpoints accept a valid `X-Authenticated-User` header without requiring `X-Auth-Signature`
