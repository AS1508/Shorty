from __future__ import annotations

import pytest

from src.core.base62 import encode
from src.core.usecases.unblock_url import UnblockUrl


class FakeRepository:
    def __init__(self, existing_ids: set[int] | None = None) -> None:
        self._ids = existing_ids or set()
        self.update_blocked_calls: list[tuple[int, bool]] = []

    async def insert(self, record): ...
    async def find_by_id(self, id): return None
    async def delete_expired(self): ...
    async def soft_delete(self, id): return 0
    async def delete_soft_deleted_older_than(self, days): return 0
    async def find_all_by_created_by(self, created_by, cursor, limit): return []
    async def find_all(self, cursor, limit): return []

    async def update_blocked(self, id: int, blocked: bool) -> int:
        self.update_blocked_calls.append((id, blocked))
        return 1 if id in self._ids else 0


class FakeCache:
    def __init__(self) -> None:
        self.delete_calls: list[str] = []

    async def get(self, key): return None
    async def set(self, key, value, ttl): pass
    async def incr(self, key): return 1
    async def expire(self, key, ttl): pass

    async def delete(self, key: str) -> None:
        self.delete_calls.append(key)

    async def aclose(self): ...


async def test_unblocks_existing_url() -> None:
    sid = 42
    repo = FakeRepository({sid})
    cache = FakeCache()
    use_case = UnblockUrl(repo, cache)

    result = await use_case.execute(encode(sid))

    assert result is True
    assert repo.update_blocked_calls == [(sid, False)]
    assert cache.delete_calls == [str(sid)]


async def test_returns_false_for_nonexistent_url() -> None:
    repo = FakeRepository()
    cache = FakeCache()
    use_case = UnblockUrl(repo, cache)

    result = await use_case.execute(encode(99))

    assert result is False


async def test_cache_eviction_errors_are_swallowed() -> None:
    sid = 42

    class FaultyCache:
        async def get(self, key): return None
        async def set(self, key, value, ttl): pass
        async def incr(self, key): return 1
        async def expire(self, key, ttl): pass

        async def delete(self, key: str) -> None:
            raise ConnectionError("simulated")

        async def aclose(self): ...

    repo = FakeRepository({sid})
    cache = FaultyCache()
    use_case = UnblockUrl(repo, cache)

    result = await use_case.execute(encode(sid))

    assert result is True


async def test_invalid_base62_raises_value_error() -> None:
    repo = FakeRepository()
    cache = FakeCache()
    use_case = UnblockUrl(repo, cache)

    with pytest.raises(ValueError, match="invalid base62 character"):
        await use_case.execute("!!!")
