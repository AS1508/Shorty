from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class UrlRecord:
    id: int
    original_url: str
    created_at: datetime
    expires_at: datetime
    is_blocked: bool = field(default=False)
    created_by: str | None = field(default=None)


class IdGenerator(Protocol):
    def next_id(self) -> int: ...


class UrlRepository(Protocol):
    async def insert(self, record: UrlRecord) -> None: ...
    async def find_by_id(self, id: int) -> UrlRecord | None: ...
    async def delete_expired(self) -> None: ...


class CachePort(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int) -> None: ...
