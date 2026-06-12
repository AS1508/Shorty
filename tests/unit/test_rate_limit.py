from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.rate_limit import FixedWindowRateLimiter


@pytest.fixture
def mock_cache() -> MagicMock:
    cache = MagicMock()
    cache.incr = AsyncMock()
    cache.expire = AsyncMock()
    return cache


@pytest.fixture
def limiter(mock_cache: MagicMock) -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(
        cache=mock_cache,
        key_prefix="rate:test",
        limit=5,
        window_seconds=60,
    )


async def test_within_limit_allows_request(limiter: FixedWindowRateLimiter, mock_cache: MagicMock) -> None:
    mock_cache.incr.return_value = 3
    result = await limiter.check("client-a")
    assert result.allowed is True
    assert result.retry_after_seconds == 0
    mock_cache.expire.assert_awaited_once()


async def test_at_limit_allows_request(limiter: FixedWindowRateLimiter, mock_cache: MagicMock) -> None:
    mock_cache.incr.return_value = 5
    result = await limiter.check("client-a")
    assert result.allowed is True


async def test_exceeding_limit_blocks_request(limiter: FixedWindowRateLimiter, mock_cache: MagicMock) -> None:
    mock_cache.incr.return_value = 6
    result = await limiter.check("client-a")
    assert result.allowed is False
    assert result.retry_after_seconds > 0


async def test_retry_after_is_remaining_window_seconds(
    limiter: FixedWindowRateLimiter, mock_cache: MagicMock, mocker: MagicMock
) -> None:
    mock_cache.incr.return_value = 10
    mocker.patch("time.time", return_value=130)
    result = await limiter.check("client-a")
    assert result.retry_after_seconds == 50


async def test_fail_open_when_redis_returns_none(
    limiter: FixedWindowRateLimiter, mock_cache: MagicMock
) -> None:
    mock_cache.incr.return_value = None
    result = await limiter.check("client-a")
    assert result.allowed is True
    mock_cache.expire.assert_not_awaited()


def test_extract_ip_single_proxy() -> None:
    ip = FixedWindowRateLimiter.extract_client_ip(
        forwarded="203.0.113.5", client_host=None
    )
    assert ip == "203.0.113.5"


def test_extract_ip_multiple_proxies() -> None:
    ip = FixedWindowRateLimiter.extract_client_ip(
        forwarded="10.0.0.1, 203.0.113.5", client_host=None
    )
    assert ip == "203.0.113.5"


def test_extract_ip_multiple_proxies_with_spaces() -> None:
    ip = FixedWindowRateLimiter.extract_client_ip(
        forwarded="10.0.0.1 , 203.0.113.5", client_host=None
    )
    assert ip == "203.0.113.5"


def test_extract_ip_no_forwarded_header() -> None:
    ip = FixedWindowRateLimiter.extract_client_ip(
        forwarded=None, client_host="192.168.1.1"
    )
    assert ip == "192.168.1.1"


def test_extract_ip_no_header_no_client() -> None:
    ip = FixedWindowRateLimiter.extract_client_ip(
        forwarded=None, client_host=None
    )
    assert ip == "unknown"


def test_extract_ip_single_ip_no_client() -> None:
    ip = FixedWindowRateLimiter.extract_client_ip(
        forwarded="203.0.113.5", client_host=None
    )
    assert ip == "203.0.113.5"


async def test_new_window_resets_counter(
    limiter: FixedWindowRateLimiter, mock_cache: MagicMock, mocker: MagicMock
) -> None:
    call_count = 0
    async def side_effect(_key: str) -> int:
        nonlocal call_count
        call_count += 1
        return 1
    mock_cache.incr.side_effect = side_effect

    mocker.patch("time.time", return_value=0)
    result1 = await limiter.check("client-a")
    assert result1.allowed is True

    mocker.patch("time.time", return_value=60)
    result2 = await limiter.check("client-a")
    assert result2.allowed is True
    assert call_count == 2
