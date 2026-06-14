from __future__ import annotations

from datetime import datetime

import pytest

from src.core.base62 import decode
from src.core.ports import UrlRecord
from src.core.usecases.create_short_url import CreateShortURL


class FakeIdGenerator:
    def __init__(self, ids: list[int]) -> None:
        self._ids = list(ids)
        self.calls = 0

    def next_id(self) -> int:
        self.calls += 1
        return self._ids.pop(0)


class FakeRepository:
    def __init__(self) -> None:
        self.records: list[UrlRecord] = []
        self.fail_with: Exception | None = None

    async def insert(self, record: UrlRecord) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.records.append(record)

    async def find_by_id(self, id: int) -> UrlRecord | None:  # noqa: ARG002
        return None

    async def delete_expired(self) -> None:
        pass

    async def soft_delete(self, id: int) -> int:
        return 0

    async def delete_soft_deleted_older_than(self, days: int) -> int:
        return 0


class FakeCache:
    async def get(self, key: str) -> str | None:  # noqa: ARG002
        return None

    async def set(self, key: str, value: str, ttl: int) -> None:  # noqa: ARG002
        pass

    async def incr(self, key: str) -> int | None:  # noqa: ARG002
        return 1

    async def expire(self, key: str, ttl: int) -> None:  # noqa: ARG002
        pass

    async def delete(self, key: str) -> None:  # noqa: ARG002
        pass

    async def aclose(self) -> None:
        pass


async def test_returns_short_url_with_decodable_code() -> None:
    gen = FakeIdGenerator([123_456_789_012_345])
    repo = FakeRepository()
    cache = FakeCache()
    use_case = CreateShortURL(gen, repo, "https://sho.rt", cache)

    short_url = await use_case.execute("https://example.com/long")

    assert short_url.startswith("https://sho.rt/")
    code = short_url.rsplit("/", 1)[-1]
    assert decode(code) == 123_456_789_012_345
    assert len(repo.records) == 1
    assert repo.records[0].original_url == "https://example.com/long"
    assert isinstance(repo.records[0].created_at, datetime)


async def test_trailing_slash_in_base_url_is_stripped() -> None:
    gen = FakeIdGenerator([1])
    repo = FakeRepository()
    cache = FakeCache()
    use_case = CreateShortURL(gen, repo, "https://sho.rt/", cache)

    short_url = await use_case.execute("https://example.com")

    assert short_url == "https://sho.rt/1"


async def test_repository_failure_propagates_and_no_url_returned() -> None:
    gen = FakeIdGenerator([42])
    repo = FakeRepository()
    repo.fail_with = RuntimeError("db down")
    cache = FakeCache()
    use_case = CreateShortURL(gen, repo, "https://sho.rt", cache)

    with pytest.raises(RuntimeError, match="db down"):
        await use_case.execute("https://example.com")
    assert repo.records == []
