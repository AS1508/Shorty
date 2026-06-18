## Why

Users have no visibility into how many times their short links have been clicked. For any business use case — marketing campaigns, internal communications, shared resources — knowing engagement is essential. Without analytics, the URL shortener is a black box after creation.

## What Changes

- **`clicks` column**: New `BIGINT NOT NULL DEFAULT 0` column on the `urls` table. Alembic migration required.
- **Click increment on redirect**: `GET /{short_code}` increments the click counter atomically when resolving a valid (non-blocked, non-expired, non-deleted) URL.
- **`GET /my-urls/{short_code}` response**: Now includes `clicks` field in the detail response (already returned by the existing endpoint).
- **`GET /my-urls` list response**: Each item includes `clicks` count.
- **`GET /admin/stats/{short_code}`**: Admin can view click stats for any URL.

Clicks are incremented after rate-limit check but before the redirect response, and failures to increment are silent (don't block the redirect).

No breaking changes. The new field is additive in all responses.

## Capabilities

### New Capabilities

- `click-analytics`: Every successful redirect increments a per-URL click counter. Users can view click counts for their own URLs via the existing list/detail endpoints and admins can view any URL's stats.

### Modified Capabilities

*(None — the click counter is additive to existing responses, no existing contracts change.)*

## Impact

- **New files**: `alembic/versions/<rev>_add_clicks_column.py`
- **Modified files**: `src/infra/db/models.py` (add `clicks` column), `src/core/ports.py` (`UrlRecord` + `increment_clicks` method), `src/infra/db/repository.py` (implement `increment_clicks`), `src/core/usecases/resolve_url.py` (increment on redirect), `src/api/routes/my_urls.py` (include `clicks` in response), `src/api/routes/admin.py` (include in admin list)
- **API surface**: New field `clicks` in `/my-urls` and `/my-urls/{short_code}` responses. New `GET /admin/stats/{short_code}`.
- **Dependencies**: None
- **Tests**: Unit test for click increment logic, integration tests verifying counter increments and appears in responses
