from __future__ import annotations

from datetime import UTC, datetime, timedelta

URL_TTL_SECONDS = 5_184_000  # 60 days = 60 * 24 * 3600
CLEANUP_INTERVAL_SECONDS = 3600  # 1 hour


def calculate_expires_at(created_at: datetime) -> datetime:
    return created_at + timedelta(seconds=URL_TTL_SECONDS)


def is_expired(expires_at: datetime) -> bool:
    now = datetime.now(UTC)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= now
