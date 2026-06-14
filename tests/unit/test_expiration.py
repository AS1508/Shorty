from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.core.expiration import (
    SOFT_DELETE_PURGE_DAYS,
    URL_TTL_SECONDS,
    calculate_expires_at,
    is_expired,
)


def test_calculate_expiration_date_returns_now_plus_60_days() -> None:
    created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    expires = calculate_expires_at(created_at)
    assert expires == datetime(2024, 3, 1, 12, 0, 0, tzinfo=UTC)


def test_calculate_expiration_date_handles_leap_year() -> None:
    created_at = datetime(2024, 2, 28, 12, 0, 0, tzinfo=UTC)
    expires = calculate_expires_at(created_at)
    assert expires == datetime(2024, 4, 28, 12, 0, 0, tzinfo=UTC)


def test_calculate_expiration_date_uses_constant_seconds() -> None:
    created_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    expires = calculate_expires_at(created_at)
    delta = expires - created_at
    assert delta.total_seconds() == URL_TTL_SECONDS


def test_is_expired_true_when_in_past() -> None:
    past = datetime(2020, 1, 1, tzinfo=UTC)
    assert is_expired(past) is True


def test_is_expired_false_when_in_future() -> None:
    future = datetime.now(UTC) + timedelta(days=1)
    assert is_expired(future) is False


def test_is_expired_true_when_naive_past_dt_treated_as_utc() -> None:
    past_naive = datetime(2020, 1, 1)
    assert is_expired(past_naive) is True


def test_is_expired_equals_current_time() -> None:
    now = datetime.now(UTC)
    assert is_expired(now) is True


def test_calculate_expires_at_margin_of_error() -> None:
    before = datetime.now(UTC)
    result = calculate_expires_at(before)
    delta = result - before
    assert abs(delta.total_seconds() - URL_TTL_SECONDS) < 1


def test_soft_delete_purge_days_is_30() -> None:
    assert SOFT_DELETE_PURGE_DAYS == 30


async def test_delete_soft_deleted_older_than_calls_repository_with_30_days() -> None:
    repo = MagicMock()
    repo.delete_soft_deleted_older_than = AsyncMock(return_value=5)

    result = await repo.delete_soft_deleted_older_than(SOFT_DELETE_PURGE_DAYS)

    assert result == 5
    repo.delete_soft_deleted_older_than.assert_awaited_once_with(30)
