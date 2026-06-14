# url-expiration Delta Specification

## ADDED Requirements

### Requirement: Background cleanup purges soft-deleted rows after a grace period
The system SHALL run a periodic background task that, in addition to deleting rows whose `expires_at <= now(UTC)`, also deletes rows whose `deleted_at IS NOT NULL AND deleted_at <= now(UTC) - interval '30 days'`.

#### Scenario: Worker purges long-soft-deleted rows
- **WHEN** the cleanup worker executes a purge cycle
- **AND** there are rows in the `urls` table with `deleted_at` more than 30 days in the past
- **THEN** those rows are deleted from the database
- **AND** rows with `deleted_at` of 30 days or less are not affected

#### Scenario: Worker keeps recent soft-deleted rows within the grace period
- **WHEN** the cleanup worker executes a purge cycle
- **AND** there are rows in the `urls` table with `deleted_at` of 30 days or less
- **THEN** those rows are not deleted

#### Scenario: Expired-but-not-deleted rows are still purged by the same worker
- **WHEN** the cleanup worker executes a purge cycle
- **AND** there are rows in the `urls` table with `expires_at <= now(UTC)` and `deleted_at IS NULL`
- **THEN** those rows are deleted by the same cycle (existing behavior, unchanged)

#### Scenario: Worker handles empty result sets without error
- **WHEN** the cleanup worker executes a purge cycle
- **AND** no rows match either the `expires_at` or the `deleted_at` purge conditions
- **THEN** the worker completes without error
- **AND** no rows are deleted
