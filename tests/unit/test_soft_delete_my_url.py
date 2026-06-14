from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.core.base62 import encode
from src.core.ports import UrlRecord
from src.core.usecases.soft_delete_my_url import SoftDeleteMyUrl


class FakeRepository:
    def __init__(self, records: list[UrlRecord] | None = None) -> None:
        self._records: dict[int, UrlRecord] = {}
        if records:
            for r in records:
                self._records[r.id] = r
        self.soft_delete_calls: list[int] = []

    async def insert(self, record: UrlRecord) -> None:
        self._records[record.id] = record

    async def find_by_id(self, id: int) -> UrlRecord | None:
        return self._records.get(id)

    async def delete_expired(self) -> None: ...

    async def soft_delete(self, id: int) -> int:
        self.soft_delete_calls.append(id)
        return 1

    async def delete_soft_deleted_older_than(self, days: int) -> int:
        return 0


class FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.delete_calls: list[str] = []
        self._fail_delete = False

    def set_fail_delete(self) -> None:
        self._fail_delete = True

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:  # noqa: ARG002
        self._store[key] = value

    async def incr(self, key: str) -> int | None:  # noqa: ARG002
        return 1

    async def expire(self, key: str, ttl: int) -> None:  # noqa: ARG002
        pass

    async def delete(self, key: str) -> None:
        if self._fail_delete:
            raise ConnectionError("simulated")
        self.delete_calls.append(key)
        self._store.pop(key, None)

    async def aclose(self) -> None: ...


def _make_record(id: int, *, created_by: str, deleted_at: datetime | None = None) -> UrlRecord:
    now = datetime.now(UTC)
    return UrlRecord(
        id=id,
        original_url=f"https://example.com/{id}",
        created_at=now,
        expires_at=now + timedelta(days=60),
        created_by=created_by,
        deleted_at=deleted_at,
    )


async def test_soft_deletes_own_url() -> None:
    record = _make_record(42, created_by="a@b.com")
    repo = FakeRepository([record])
    cache = FakeCache()
    use_case = SoftDeleteMyUrl(repository=repo, cache=cache)

    await use_case.execute(encode(42), "a@b.com")

    assert repo.soft_delete_calls == [42]
    assert cache.delete_calls == ["42"]


async def test_returns_silently_on_missing_record() -> None:
    repo = FakeRepository([])
    cache = FakeCache()
    use_case = SoftDeleteMyUrl(repository=repo, cache=cache)

    await use_case.execute(encode(99), "a@b.com")

    assert repo.soft_delete_calls == []
    assert cache.delete_calls == []


async def test_returns_silently_on_ownership_mismatch() -> None:
    record = _make_record(42, created_by="a@b.com")
    repo = FakeRepository([record])
    cache = FakeCache()
    use_case = SoftDeleteMyUrl(repository=repo, cache=cache)

    await use_case.execute(encode(42), "other@b.com")

    assert repo.soft_delete_calls == []
    assert cache.delete_calls == []


async def test_returns_silently_when_already_deleted() -> None:
    record = _make_record(42, created_by="a@b.com", deleted_at=datetime.now(UTC))
    repo = FakeRepository([record])
    cache = FakeCache()
    use_case = SoftDeleteMyUrl(repository=repo, cache=cache)

    await use_case.execute(encode(42), "a@b.com")

    assert repo.soft_delete_calls == []
    assert cache.delete_calls == []


async def test_raises_value_error_on_invalid_code() -> None:
    repo = FakeRepository([])
    cache = FakeCache()
    use_case = SoftDeleteMyUrl(repository=repo, cache=cache)

    with pytest.raises(ValueError, match="invalid base62 character"):
        await use_case.execute("!!!", "a@b.com")


async def test_cache_delete_error_is_swallowed() -> None:
    record = _make_record(42, created_by="a@b.com")
    repo = FakeRepository([record])
    cache = FakeCache()
    cache.set_fail_delete()
    use_case = SoftDeleteMyUrl(repository=repo, cache=cache)

    await use_case.execute(encode(42), "a@b.com")

    assert repo.soft_delete_calls == [42]
