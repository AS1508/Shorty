# url-redirect Delta Specification

## ADDED Requirements

### Requirement: Return 410 Gone for soft-deleted URLs
The system SHALL respond with HTTP `410 Gone` when a `GET /{short_code}` request resolves a short code whose corresponding row in the `urls` table has a non-NULL `deleted_at` value. The response body SHALL be a JSON object `{"detail": "..."}` with a generic gone message that does not distinguish "deleted" from "expired".

#### Scenario: Soft-deleted URL returns 410
- **WHEN** a client sends `GET /{short_code}` and the corresponding row has `deleted_at IS NOT NULL` regardless of `expires_at` or `is_blocked`
- **THEN** the system responds with status `410` and a body `{"detail": "..."}` indicating the short link is gone
- **AND** the `Location` header is not set

#### Scenario: Soft-deleted URL caches a deleted sentinel
- **WHEN** the system resolves a soft-deleted URL from the database (cache miss) and writes the resolution to the cache
- **THEN** the cache entry SHALL be a `DELETED` sentinel with a TTL of no more than 300 seconds
- **AND** subsequent requests within that TTL respond with `410` without querying the database

#### Scenario: Cache is not poisoned by a fresh soft delete
- **WHEN** an authenticated user soft-deletes a URL and the URL was previously cached as a positive record
- **THEN** the positive cache entry is removed by the delete operation
- **AND** the next `GET /{short_code}` does not serve a stale `302` redirect from cache
