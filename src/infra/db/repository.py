from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.ports import UrlRecord
from src.infra.db.models import Url


class SqlAlchemyUrlRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, record: UrlRecord) -> None:
        row = Url(
            id=record.id,
            original_url=record.original_url,
            created_at=record.created_at,
            is_blocked=record.is_blocked,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.commit()

    async def find_by_id(self, id: int) -> UrlRecord | None:
        result = await self._session.execute(select(Url).where(Url.id == id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return UrlRecord(
            id=row.id,
            original_url=row.original_url,
            created_at=row.created_at,
            is_blocked=row.is_blocked,
        )
