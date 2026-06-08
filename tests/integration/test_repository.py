from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.ports import UrlRecord
from src.infra.db.models import Base, Url
from src.infra.db.repository import SqlAlchemyUrlRepository


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_insert_persists_row(session: AsyncSession) -> None:
    repo = SqlAlchemyUrlRepository(session)
    record = UrlRecord(
        id=12345,
        original_url="https://example.com",
        created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        expires_at=datetime(2024, 3, 1, 0, 0, 0, tzinfo=UTC),
    )
    await repo.insert(record)
    await session.commit()

    result = await session.execute(select(Url))
    rows = list(result.scalars())
    assert len(rows) == 1
    assert rows[0].id == 12345
    assert rows[0].original_url == "https://example.com"
    assert rows[0].created_at == datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC).replace(tzinfo=None)
