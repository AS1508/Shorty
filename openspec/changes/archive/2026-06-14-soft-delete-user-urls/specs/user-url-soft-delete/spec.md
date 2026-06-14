# user-url-soft-delete Specification

## Purpose
TBD - created by archiving change soft-delete-user-urls. Update Purpose after archive.

## ADDED Requirements

### Requirement: Authenticated user can soft-delete own URL
The system SHALL accept a `DELETE` request at `/my-urls/{short_code}` from an authenticated user (identified by the `X-Authenticated-User` header) and, when the short code decodes to a stored URL whose `created_by` matches the authenticated user's email and whose `deleted_at` is `NULL`, respond with HTTP `204 No Content` and set `deleted_at` to the current UTC timestamp on that row.

#### Scenario: User soft-deletes their own URL
- **WHEN** an authenticated client sends `DELETE /my-urls/{code}` and the decoded short code corresponds to a row in the `urls` table with `created_by` equal to the authenticated email and `deleted_at IS NULL`
- **THEN** the system responds with status `204` and an empty body
- **AND** the `deleted_at` column of that row is set to the current UTC timestamp

#### Scenario: User cannot soft-delete a URL owned by another user
- **WHEN** an authenticated client sends `DELETE /my-urls/{code}` and the corresponding row's `created_by` does not match the authenticated email
- **THEN** the system responds with status `404`
- **AND** no row in the `urls` table is modified

#### Scenario: User cannot soft-delete a non-existent URL
- **WHEN** an authenticated client sends `DELETE /my-urls/{code}` and the decoded short code does not correspond to any row in the `urls` table
- **THEN** the system responds with status `404`
- **AND** no row is created or modified

#### Scenario: Soft-deleting an already-deleted URL is idempotent
- **WHEN** an authenticated client sends `DELETE /my-urls/{code}` and the corresponding row's `deleted_at` is not `NULL`
- **THEN** the system responds with status `404`
- **AND** the existing `deleted_at` value is preserved unchanged

#### Scenario: Unauthenticated request is rejected
- **WHEN** a client sends `DELETE /my-urls/{code}` without the `X-Authenticated-User` header
- **THEN** the system responds with status `403`
- **AND** no row in the `urls` table is modified

#### Scenario: Invalid short code format is rejected before database access
- **WHEN** a client sends `DELETE /my-urls/{code}` where `{code}` contains characters outside `[A-Za-z0-9]`
- **THEN** the system responds with status `400` and a body `{"detail": "..."}` describing the format error
- **AND** the database is not queried

### Requirement: Soft delete invalidates the cached redirect entry
The system SHALL evict the Redis cache entry associated with the deleted URL's short code as part of the soft-delete operation. If the cache is unreachable, the soft-delete SHALL still complete successfully and the cache SHALL be re-evaluated lazily on the next read.

#### Scenario: Cache is invalidated on successful soft delete
- **WHEN** an authenticated user soft-deletes a URL whose short code has a positive record cached in Redis
- **THEN** the corresponding Redis key is removed as part of the request
- **AND** a subsequent `GET /{short_code}` request queries the database, observes the `deleted_at` value, and responds with `410 Gone` (or serves a `DELETED` sentinel from the cache after rehydration)

#### Scenario: Cache outage does not prevent soft delete
- **WHEN** an authenticated user soft-deletes a URL and the Redis cache is unreachable
- **THEN** the soft-delete in the database still succeeds
- **AND** the system responds with status `204`

### Requirement: Soft delete is race-safe under concurrent requests
The system SHALL guarantee that, given two concurrent `DELETE /my-urls/{code}` requests for the same URL by the same user, exactly one request receives status `204` and the other receives status `404`, regardless of which arrives first at the database.

#### Scenario: Two concurrent deletes produce one 204 and one 404
- **WHEN** an authenticated client sends two `DELETE /my-urls/{code}` requests for the same URL in rapid succession
- **THEN** exactly one request responds with status `204`
- **AND** the other request responds with status `404`
- **AND** the `deleted_at` column of the row is set exactly once
