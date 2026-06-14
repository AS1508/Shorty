from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
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
            expires_at=record.expires_at,
            is_blocked=record.is_blocked,
            created_by=record.created_by,
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
            expires_at=row.expires_at,
            is_blocked=row.is_blocked,
            created_by=row.created_by,
            deleted_at=row.deleted_at,
        )

    async def delete_expired(self) -> None:
        from sqlalchemy.sql import func as sa_func

        stmt = delete(Url).where(Url.expires_at <= sa_func.now())
        await self._session.execute(stmt)
        await self._session.commit()

    async def soft_delete(self, id: int) -> int:
        stmt = (
            update(Url)
            .where(Url.id == id, Url.deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC))
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount  # type: ignore[no-any-return, attr-defined]

    async def delete_soft_deleted_older_than(self, days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = delete(Url).where(
            Url.deleted_at.is_not(None),
            Url.deleted_at <= cutoff,
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount  # type: ignore[no-any-return, attr-defined]
