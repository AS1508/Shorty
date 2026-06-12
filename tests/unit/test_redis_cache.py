from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.infra.cache.redis import RedisCache


@pytest.fixture
def cache() -> RedisCache:
    return RedisCache("redis://localhost:6379/0")


async def test_get_on_connection_error_returns_none(cache: RedisCache, mocker: MagicMock) -> None:
    mocker.patch.object(cache._client, "get", side_effect=RedisConnectionError("down"))
    result = await cache.get("key1")
    assert result is None


async def test_set_on_connection_error_is_silent(cache: RedisCache, mocker: MagicMock) -> None:
    mocker.patch.object(cache._client, "setex", side_effect=RedisConnectionError("down"))
    await cache.set("key1", "value", 60)


async def test_get_on_generic_error_returns_none(cache: RedisCache, mocker: MagicMock) -> None:
    mocker.patch.object(cache._client, "get", side_effect=OSError("broken"))
    result = await cache.get("key1")
    assert result is None


async def test_close_is_safe(cache: RedisCache, mocker: MagicMock) -> None:
    mocker.patch.object(cache._client, "aclose", side_effect=Exception("ignore"))
    await cache.aclose()


async def test_incr_returns_new_value(cache: RedisCache, mocker: MagicMock) -> None:
    mocker.patch.object(cache._client, "incr", new_callable=AsyncMock, return_value=1)
    result = await cache.incr("rate:key")
    assert result == 1


async def test_incr_on_connection_error_returns_none(cache: RedisCache, mocker: MagicMock) -> None:
    mocker.patch.object(cache._client, "incr", new_callable=AsyncMock, side_effect=RedisConnectionError("down"))
    result = await cache.incr("rate:key")
    assert result is None


async def test_incr_on_generic_error_returns_none(cache: RedisCache, mocker: MagicMock) -> None:
    mocker.patch.object(cache._client, "incr", new_callable=AsyncMock, side_effect=OSError("broken"))
    result = await cache.incr("rate:key")
    assert result is None
