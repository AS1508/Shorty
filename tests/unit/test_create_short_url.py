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


async def test_returns_short_url_with_decodable_code() -> None:
    gen = FakeIdGenerator([123_456_789_012_345])
    repo = FakeRepository()
    use_case = CreateShortURL(gen, repo, "https://sho.rt")

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
    use_case = CreateShortURL(gen, repo, "https://sho.rt/")

    short_url = await use_case.execute("https://example.com")

    assert short_url == "https://sho.rt/1"


async def test_repository_failure_propagates_and_no_url_returned() -> None:
    gen = FakeIdGenerator([42])
    repo = FakeRepository()
    repo.fail_with = RuntimeError("db down")
    use_case = CreateShortURL(gen, repo, "https://sho.rt")

    with pytest.raises(RuntimeError, match="db down"):
        await use_case.execute("https://example.com")
    assert repo.records == []
