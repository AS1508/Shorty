from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.core.base62 import encode
from src.core.ports import UrlRecord
from src.core.usecases.get_my_url import GetMyUrl


class FakeRepository:
    def __init__(self, records: list[UrlRecord] | None = None) -> None:
        self._records: dict[int, UrlRecord] = {}
        if records:
            for r in records:
                self._records[r.id] = r

    async def insert(self, record: UrlRecord) -> None:
        self._records[record.id] = record

    async def find_by_id(self, id: int) -> UrlRecord | None:
        return self._records.get(id)

    async def delete_expired(self) -> None: ...

    async def soft_delete(self, id: int) -> int:
        return 0

    async def delete_soft_deleted_older_than(self, days: int) -> int:
        return 0

    async def find_all_by_created_by(
        self, created_by: str, cursor: int | None, limit: int
    ) -> list[UrlRecord]:
        return []


def _record(id: int, *, created_by: str = "a@b.com") -> UrlRecord:
    now = datetime.now(UTC)
    return UrlRecord(
        id=id,
        original_url=f"https://example.com/{id}",
        created_at=now,
        expires_at=now + timedelta(days=60),
        created_by=created_by,
    )


async def test_own_url_found() -> None:
    record = _record(42, created_by="a@b.com")
    repo = FakeRepository([record])
    use_case = GetMyUrl(repo)

    result = await use_case.execute(encode(42), "a@b.com")

    assert result is not None
    assert result.id == 42
    assert result.original_url == "https://example.com/42"
    assert result.created_by == "a@b.com"


async def test_nonexistent_url_returns_none() -> None:
    repo = FakeRepository()
    use_case = GetMyUrl(repo)

    result = await use_case.execute(encode(99), "a@b.com")

    assert result is None


async def test_other_users_url_returns_none() -> None:
    record = _record(42, created_by="alice@a.com")
    repo = FakeRepository([record])
    use_case = GetMyUrl(repo)

    result = await use_case.execute(encode(42), "bob@b.com")

    assert result is None


async def test_deleted_url_found_with_deleted_at() -> None:
    now = datetime.now(UTC)
    record = UrlRecord(
        id=7,
        original_url="https://deleted.example.com",
        created_at=now,
        expires_at=now + timedelta(days=60),
        created_by="a@b.com",
        deleted_at=now,
    )
    repo = FakeRepository([record])
    use_case = GetMyUrl(repo)

    result = await use_case.execute(encode(7), "a@b.com")

    assert result is not None
    assert result.deleted_at is not None


async def test_expired_url_found() -> None:
    now = datetime.now(UTC)
    record = UrlRecord(
        id=3,
        original_url="https://expired.example.com",
        created_at=now - timedelta(days=70),
        expires_at=now - timedelta(days=10),
        created_by="a@b.com",
    )
    repo = FakeRepository([record])
    use_case = GetMyUrl(repo)

    result = await use_case.execute(encode(3), "a@b.com")

    assert result is not None
    assert result.expires_at < now


async def test_blocked_url_found() -> None:
    record = UrlRecord(
        id=5,
        original_url="https://blocked.example.com",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=60),
        is_blocked=True,
        created_by="a@b.com",
    )
    repo = FakeRepository([record])
    use_case = GetMyUrl(repo)

    result = await use_case.execute(encode(5), "a@b.com")

    assert result is not None
    assert result.is_blocked is True


async def test_invalid_base62_code_raises_value_error() -> None:
    repo = FakeRepository()
    use_case = GetMyUrl(repo)

    with pytest.raises(ValueError, match="invalid base62 character"):
        await use_case.execute("!!!", "a@b.com")
