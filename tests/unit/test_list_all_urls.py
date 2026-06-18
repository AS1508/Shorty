from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.core.ports import UrlRecord
from src.core.usecases.list_all_urls import ListAllUrls


class FakeRepository:
    def __init__(self, records: list[UrlRecord] | None = None) -> None:
        self._records: dict[int, UrlRecord] = {}
        if records:
            for r in records:
                self._records[r.id] = r

    async def insert(self, record): ...
    async def find_by_id(self, id): return self._records.get(id)
    async def delete_expired(self): ...
    async def soft_delete(self, id): return 0
    async def delete_soft_deleted_older_than(self, days): return 0

    async def find_all_by_created_by(self, created_by, cursor, limit):
        return []

    async def update_blocked(self, id, blocked):
        return 0

    async def find_all(self, cursor: int | None, limit: int) -> list[UrlRecord]:
        filtered = [
            r for r in self._records.values()
            if cursor is None or r.id < cursor
        ]
        filtered.sort(key=lambda r: r.id, reverse=True)
        return filtered[:limit]


def _record(id: int, *, created_by: str = "a@b.com") -> UrlRecord:
    now = datetime.now(UTC)
    return UrlRecord(
        id=id,
        original_url=f"https://example.com/{id}",
        created_at=now,
        expires_at=now + timedelta(days=60),
        created_by=created_by,
    )


async def test_empty_when_no_urls() -> None:
    repo = FakeRepository()
    use_case = ListAllUrls(repo)

    result = await use_case.execute(cursor=None, limit=20)

    assert result.items == []
    assert result.has_more is False


async def test_returns_all_users_urls() -> None:
    records = [
        _record(30, created_by="alice@a.com"),
        _record(20, created_by="bob@b.com"),
        _record(10, created_by="alice@a.com"),
    ]
    repo = FakeRepository(records)
    use_case = ListAllUrls(repo)

    result = await use_case.execute(cursor=None, limit=20)

    assert len(result.items) == 3
    assert {r.id for r in result.items} == {30, 20, 10}


async def test_pagination_with_cursor() -> None:
    records = [_record(i) for i in (50, 40, 30, 20, 10)]
    repo = FakeRepository(records)
    use_case = ListAllUrls(repo)

    page1 = await use_case.execute(cursor=None, limit=3)
    assert len(page1.items) == 3
    assert page1.has_more is True

    cursor = page1.items[-1].id
    page2 = await use_case.execute(cursor=cursor, limit=3)
    assert len(page2.items) == 2
    assert page2.has_more is False


async def test_includes_created_by_field() -> None:
    records = [_record(1, created_by="admin@a.com")]
    repo = FakeRepository(records)
    use_case = ListAllUrls(repo)

    result = await use_case.execute(cursor=None, limit=10)

    assert result.items[0].created_by == "admin@a.com"
