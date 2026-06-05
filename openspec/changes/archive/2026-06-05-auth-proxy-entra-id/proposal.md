## Why

Shorty is intended for internal corporate use behind Microsoft Entra ID, but today any client that can reach the service can create URLs without restriction. The service needs to trust authentication delegated to a reverse proxy (the identity-aware proxy handles Entra ID SSO) and simply read the verified user identity from the `X-Authenticated-User` header to gate creation endpoints and associate every URL with its creator.

## What Changes

- Add a FastAPI dependency (`RequireAuthenticatedUser`) that verifies the `X-Authenticated-User` header is cryptographically signed by the proxy using an HMAC-SHA256 shared secret. Returns `403 Forbidden` when the header is absent, malformed, or the `X-Auth-Signature` header does not match.
- Add `PROXY_SHARED_SECRET` to `Settings` — a shared secret known only to the reverse proxy and Shorty, used to verify the HMAC signature.
- Apply the dependency to `POST /Create-URL` so that only authenticated internal users can create short URLs.
- Add a `created_by: str | None` column to the `urls` table (nullable for backward-compatibility; populated by the route from the authenticated header).
- The public redirect endpoint `GET /{short_code}` remains untouched — no auth required.
- The reverse proxy MUST compute the HMAC and inject the `X-Auth-Signature` header. The proxy is configured externally (non-goal for this change).

## Capabilities

### New Capabilities

- `auth-proxy`: Guard for `POST /Create-URL` (and future management endpoints) that validates the `X-Authenticated-User` header and its HMAC-SHA256 signature (`X-Auth-Signature`) injected by an identity-aware proxy. Rejects requests with missing or invalid signatures with `403 Forbidden`.

### Modified Capabilities

- `url-shortening`: The "Create short URL" requirement is modified — `POST /Create-URL` SHALL require a valid `X-Authenticated-User` header and SHALL reject requests that lack it with `403 Forbidden`. When the header is present, the email value SHALL be persisted in the new `created_by` column of the `urls` table.

## Impact

- **Configuration:** New `PROXY_SHARED_SECRET` env var (string, must be identical on proxy and Shorty).
- **Database:** New nullable `created_by` column on the `urls` table (Alembic migration required).
- **Code:** New dependency in `src/api/dependencies.py`; `PROXY_SHARED_SECRET` in `src/infra/config.py`; modification to `src/api/routes/shortener.py`; new column in `src/infra/db/models.py` and `src/core/ports.py` (`UrlRecord`).
- **Routes:** `POST /Create-URL` now gated by HMAC-verified auth; `GET /{short_code}` unchanged.
- **Tests:** New integration tests for 403 path (missing header, invalid signature), updated existing tests to include valid header + signature.
- **Infra:** The reverse proxy must compute `HMAC-SHA256(secret, email)` and inject the `X-Auth-Signature` header. This is configured externally — Shorty only verifies.
