from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.core.ports import UrlRecord
from src.core.usecases.list_my_urls import ListMyUrls


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
        filtered = [
            r for r in self._records.values()
            if r.created_by == created_by and (cursor is None or r.id < cursor)
        ]
        filtered.sort(key=lambda r: r.id, reverse=True)
        return filtered[:limit]


def _record(id: int, *, created_by: str = "a@b.com") -> UrlRecord:
    now = datetime.now(UTC)
    return UrlRecord(
        id=id,
        original_url=f"https://example.com/{id}",
        created_at=now - timedelta(seconds=id),
        expires_at=now + timedelta(days=60),
        created_by=created_by,
    )


async def test_empty_list_when_no_urls() -> None:
    repo = FakeRepository()
    use_case = ListMyUrls(repo)

    result = await use_case.execute("a@b.com", cursor=None, limit=20)

    assert result.items == []
    assert result.has_more is False


async def test_single_page_within_limit() -> None:
    records = [_record(i) for i in (30, 20, 10)]
    repo = FakeRepository(records)
    use_case = ListMyUrls(repo)

    result = await use_case.execute("a@b.com", cursor=None, limit=10)

    assert len(result.items) == 3
    assert result.has_more is False
    assert [r.id for r in result.items] == [30, 20, 10]  # newest first


async def test_pagination_boundary_exact_page() -> None:
    records = [_record(i) for i in range(40, 10, -10)]  # 40, 30, 20
    repo = FakeRepository(records)
    use_case = ListMyUrls(repo)

    result = await use_case.execute("a@b.com", cursor=None, limit=3)

    assert len(result.items) == 3
    assert result.has_more is False


async def test_pagination_next_page_with_cursor() -> None:
    ids = [50, 40, 30, 20, 10]
    records = [_record(i) for i in ids]
    repo = FakeRepository(records)
    use_case = ListMyUrls(repo)

    page1 = await use_case.execute("a@b.com", cursor=None, limit=3)
    assert len(page1.items) == 3
    assert page1.has_more is True
    assert [r.id for r in page1.items] == [50, 40, 30]

    cursor = page1.items[-1].id  # 30
    page2 = await use_case.execute("a@b.com", cursor=cursor, limit=3)
    assert len(page2.items) == 2
    assert page2.has_more is False
    assert [r.id for r in page2.items] == [20, 10]


async def test_ignores_other_users() -> None:
    records = [
        _record(1, created_by="alice@a.com"),
        _record(2, created_by="bob@b.com"),
        _record(3, created_by="alice@a.com"),
    ]
    repo = FakeRepository(records)
    use_case = ListMyUrls(repo)

    result = await use_case.execute("alice@a.com", cursor=None, limit=10)

    assert len(result.items) == 2
    assert {r.id for r in result.items} == {1, 3}
    assert all(r.created_by == "alice@a.com" for r in result.items)


async def test_cursor_nonexistent_id_returns_empty() -> None:
    records = [_record(i) for i in (10, 5, 3)]
    repo = FakeRepository(records)
    use_case = ListMyUrls(repo)

    result = await use_case.execute("a@b.com", cursor=2, limit=10)

    assert result.items == []
    assert result.has_more is False


async def test_items_include_is_expired() -> None:
    now = datetime.now(UTC)
    expired = UrlRecord(
        id=1,
        original_url="https://expired.example.com",
        created_at=now - timedelta(days=70),
        expires_at=now - timedelta(days=10),
        created_by="a@b.com",
    )
    active = _record(2)
    repo = FakeRepository([expired, active])
    use_case = ListMyUrls(repo)

    result = await use_case.execute("a@b.com", cursor=None, limit=10)

    assert len(result.items) == 2
    expired_item = next(r for r in result.items if r.id == 1)
    active_item = next(r for r in result.items if r.id == 2)
    assert expired_item.is_expired is True
    assert active_item.is_expired is False


async def test_items_include_deleted_at_and_blocked() -> None:
    now = datetime.now(UTC)
    deleted = UrlRecord(
        id=1,
        original_url="https://deleted.example.com",
        created_at=now,
        expires_at=now + timedelta(days=60),
        is_blocked=False,
        created_by="a@b.com",
        deleted_at=now,
    )
    blocked = UrlRecord(
        id=2,
        original_url="https://blocked.example.com",
        created_at=now,
        expires_at=now + timedelta(days=60),
        is_blocked=True,
        created_by="a@b.com",
    )
    repo = FakeRepository([deleted, blocked])
    use_case = ListMyUrls(repo)

    result = await use_case.execute("a@b.com", cursor=None, limit=10)

    assert len(result.items) == 2
    deleted_item = next(r for r in result.items if r.id == 1)
    blocked_item = next(r for r in result.items if r.id == 2)
    assert deleted_item.deleted_at is not None
    assert deleted_item.is_blocked is False
    assert blocked_item.is_blocked is True
    assert blocked_item.deleted_at is None
