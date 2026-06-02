from __future__ import annotations

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
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.commit()
