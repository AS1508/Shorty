from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.core.base62 import encode
from src.core.ports import UrlRecord
from src.core.usecases.resolve_url import ResolveStatus, ResolveURL


class FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.get_calls = 0
        self.set_calls = 0
        self._fail_on: str | None = None

    def fail_on(self, method: str) -> None:
        self._fail_on = method

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        if self._fail_on == "get":
            raise ConnectionError("simulated")
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:  # noqa: ARG002
        self.set_calls += 1
        if self._fail_on == "set":
            raise ConnectionError("simulated")
        self._store[key] = value


class FakeRepository:
    def __init__(self, records: dict[int, UrlRecord] | None = None) -> None:
        self._records: dict[int, UrlRecord] = records or {}
        self.find_calls = 0

    async def insert(self, record: UrlRecord) -> None:
        pass

    async def find_by_id(self, id: int) -> UrlRecord | None:
        self.find_calls += 1
        return self._records.get(id)

    async def delete_expired(self) -> None:
        pass


def _record(snowflake_id: int, url: str = "https://example.com", *, blocked: bool = False) -> UrlRecord:
    return UrlRecord(
        id=snowflake_id,
        original_url=url,
        is_blocked=blocked,
        created_at=datetime.now(UTC) - timedelta(days=1),
        expires_at=datetime.now(UTC) + timedelta(days=60),
    )


def _code(snowflake_id: int) -> str:
    return encode(snowflake_id)


SID = 12345
CODE = _code(SID)


async def test_cache_hit_skips_db() -> None:
    repo = FakeRepository()
    cache = FakeCache()
    cache._store[str(SID)] = '{"s":"ok","u":"https://cached.example.com"}'
    use_case = ResolveURL(repository=repo, cache=cache)

    result = await use_case.execute(CODE)

    assert result.status == ResolveStatus.OK
    assert result.url == "https://cached.example.com"
    assert cache.get_calls == 1
    assert repo.find_calls == 0


async def test_db_found_and_cache_populated() -> None:
    repo = FakeRepository({SID: _record(SID)})
    cache = FakeCache()
    use_case = ResolveURL(repository=repo, cache=cache)

    result = await use_case.execute(CODE)

    assert result.status == ResolveStatus.OK
    assert result.url == "https://example.com"
    assert repo.find_calls == 1
    assert cache.set_calls == 1
    assert str(SID) in cache._store


async def test_db_not_found_returns_404() -> None:
    repo = FakeRepository()
    cache = FakeCache()
    use_case = ResolveURL(repository=repo, cache=cache)

    result = await use_case.execute(CODE)

    assert result.status == ResolveStatus.NOT_FOUND
    assert result.url is None


async def test_not_found_caches_negative_sentinel() -> None:
    repo = FakeRepository()
    cache = FakeCache()
    use_case = ResolveURL(repository=repo, cache=cache)

    await use_case.execute(CODE)

    assert cache.set_calls == 1
    assert str(SID) in cache._store

    await use_case.execute(CODE)

    assert repo.find_calls == 1
    assert cache.get_calls == 2  # second was cache hit


async def test_blocked_returns_403() -> None:
    repo = FakeRepository({SID: _record(SID, blocked=True)})
    cache = FakeCache()
    use_case = ResolveURL(repository=repo, cache=cache)

    result = await use_case.execute(CODE)

    assert result.status == ResolveStatus.BLOCKED


async def test_cache_failure_falls_through_to_db() -> None:
    repo = FakeRepository({SID: _record(SID)})
    cache = FakeCache()
    cache.fail_on("get")
    use_case = ResolveURL(repository=repo, cache=cache)

    result = await use_case.execute(CODE)

    assert result.status == ResolveStatus.OK
    assert result.url == "https://example.com"


async def test_decode_failure_raises_value_error() -> None:
    repo = FakeRepository()
    cache = FakeCache()
    use_case = ResolveURL(repository=repo, cache=cache)

    with pytest.raises(ValueError):
        await use_case.execute("!not-base62!")
