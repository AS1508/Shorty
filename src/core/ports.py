from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class UrlRecord:
    id: int
    original_url: str
    created_at: datetime


class IdGenerator(Protocol):
    def next_id(self) -> int: ...


class UrlRepository(Protocol):
    async def insert(self, record: UrlRecord) -> None: ...
