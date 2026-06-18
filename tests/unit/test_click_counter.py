from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.core.base62 import encode
from src.core.ports import UrlRecord
from src.core.usecases.resolve_url import ResolveStatus, ResolveURL


class FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:
        self._store[key] = value

    async def incr(self, key: str) -> int | None:
        return 1

    async def expire(self, key: str, ttl: int) -> None:
        pass

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def aclose(self) -> None:
        pass


class FakeRepository:
    def __init__(self, records: dict[int, UrlRecord] | None = None) -> None:
        self._records: dict[int, UrlRecord] = records or {}
        self.increment_calls: list[int] = []

    async def insert(self, record): ...
    async def find_by_id(self, id: int) -> UrlRecord | None:
        return self._records.get(id)
    async def delete_expired(self): ...
    async def soft_delete(self, id): return 0
    async def delete_soft_deleted_older_than(self, days): return 0
    async def find_all_by_created_by(self, created_by, cursor, limit): return []
    async def find_all(self, cursor, limit): return []
    async def update_blocked(self, id, blocked): return 0

    async def increment_clicks(self, id: int) -> None:
        self.increment_calls.append(id)


def _record(sid: int, **kw: object) -> UrlRecord:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": sid,
        "original_url": f"https://example.com/{sid}",
        "created_at": now,
        "expires_at": now + timedelta(days=60),
    }
    defaults.update(kw)
    return UrlRecord(**defaults)  # type: ignore[arg-type]


async def test_increments_clicks_on_valid_resolve() -> None:
    sid = 42
    repo = FakeRepository({sid: _record(sid)})
    cache = FakeCache()
    use_case = ResolveURL(repository=repo, cache=cache)

    result = await use_case.execute(encode(sid))

    assert result.status == ResolveStatus.OK
    assert repo.increment_calls == [sid]


async def test_does_not_increment_on_not_found() -> None:
    repo = FakeRepository()
    cache = FakeCache()
    use_case = ResolveURL(repository=repo, cache=cache)

    await use_case.execute(encode(99))

    assert repo.increment_calls == []


async def test_does_not_increment_on_blocked() -> None:
    sid = 42
    repo = FakeRepository({sid: _record(sid, is_blocked=True)})
    cache = FakeCache()
    use_case = ResolveURL(repository=repo, cache=cache)

    await use_case.execute(encode(sid))

    assert repo.increment_calls == []


async def test_does_not_increment_on_expired() -> None:
    sid = 42
    now = datetime.now(UTC)
    repo = FakeRepository({sid: _record(sid, expires_at=now - timedelta(days=1))})
    cache = FakeCache()
    use_case = ResolveURL(repository=repo, cache=cache)

    await use_case.execute(encode(sid))

    assert repo.increment_calls == []


async def test_does_not_increment_on_deleted() -> None:
    sid = 42
    repo = FakeRepository({sid: _record(sid, deleted_at=datetime.now(UTC))})
    cache = FakeCache()
    use_case = ResolveURL(repository=repo, cache=cache)

    await use_case.execute(encode(sid))

    assert repo.increment_calls == []


async def test_increment_failure_does_not_block_resolve() -> None:
    sid = 42

    class FaultyRepo:
        async def insert(self, record): ...
        async def find_by_id(self, id): return _record(sid)
        async def delete_expired(self): ...
        async def soft_delete(self, id): return 0
        async def delete_soft_deleted_older_than(self, days): return 0
        async def find_all_by_created_by(self, created_by, cursor, limit): return []
        async def find_all(self, cursor, limit): return []
        async def update_blocked(self, id, blocked): return 0

        async def increment_clicks(self, id: int) -> None:
            raise RuntimeError("db down")

    repo = FaultyRepo()
    cache = FakeCache()
    use_case = ResolveURL(repository=repo, cache=cache)

    result = await use_case.execute(encode(sid))

    assert result.status == ResolveStatus.OK
