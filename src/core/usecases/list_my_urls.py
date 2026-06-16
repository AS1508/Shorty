from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.core.expiration import is_expired
from src.core.ports import UrlRepository


@dataclass(frozen=True, slots=True)
class ListMyUrlsItem:
    id: int
    original_url: str
    created_at: datetime
    expires_at: datetime
    is_expired: bool
    is_blocked: bool
    created_by: str | None
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class ListMyUrlsResult:
    items: list[ListMyUrlsItem]
    has_more: bool


class ListMyUrls:
    def __init__(self, repository: UrlRepository) -> None:
        self._repository = repository

    async def execute(
        self, created_by: str, cursor: int | None, limit: int
    ) -> ListMyUrlsResult:
        records = await self._repository.find_all_by_created_by(
            created_by, cursor, limit + 1
        )
        has_more = len(records) > limit
        if has_more:
            records = records[:limit]

        items = [
            ListMyUrlsItem(
                id=r.id,
                original_url=r.original_url,
                created_at=r.created_at,
                expires_at=r.expires_at,
                is_expired=is_expired(r.expires_at),
                is_blocked=r.is_blocked,
                created_by=r.created_by,
                deleted_at=r.deleted_at,
            )
            for r in records
        ]
        return ListMyUrlsResult(items=items, has_more=has_more)
