from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import AppState, set_app_state
from src.api.main import create_app
from src.infra.config import Settings
from src.infra.db.models import Base, Url

AUTH_HEADER = {"X-Authenticated-User": "test@test.com"}


class FakeCacheForExpirationTest:
    """In-memory cache double that tracks set calls with TTL."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int]] = []
        self._fail: bool = False

    def set_fail(self, fail: bool) -> None:
        self._fail = fail

    async def get(self, key: str) -> str | None:
        if self._fail:
            return None
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:
        self.set_calls.append((key, value, ttl))
        self._store[key] = value

    async def incr(self, key: str) -> int | None:  # noqa: ARG002
        if self._fail:
            return None
        return 1

    async def expire(self, key: str, ttl: int) -> None:  # noqa: ARG002
        pass

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def aclose(self) -> None:
        pass

    async def close(self) -> None:
        await self.aclose()


def _make_state(test_db: str) -> AppState:
    settings = Settings(
        database_url=test_db,
        short_base_url="https://sho.rt",
        snowflake_node_id=0,
    )
    state = AppState(settings)
    state.cache = FakeCacheForExpirationTest()
    return state


@pytest_asyncio.fixture
async def app_state() -> AsyncIterator[AppState]:
    test_db = "sqlite+aiosqlite:///:memory:"
    state = _make_state(test_db)
    async with state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    set_app_state(state)
    try:
        yield state
    finally:
        await state.dispose()
        set_app_state(None)


@pytest_asyncio.fixture
async def client(app_state: AppState) -> AsyncIterator[AsyncClient]:
    app = create_app(state=app_state)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_create_url_persists_expires_at(client: AsyncClient, app_state: AppState) -> None:

    from sqlalchemy import select

    response = await client.post(
        "/Create-URL",
        json={"url": "https://example.com/expiry-test"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 201

    async with app_state.session_factory() as session:
        result = await session.execute(select(Url))
        rows = list(result.scalars())
    assert len(rows) == 1
    row = rows[0]
    assert row.expires_at is not None
    # 60 days = 5_184_000 seconds; allow 2 seconds margin for test execution
    delta = (row.expires_at - row.created_at).total_seconds()
    assert abs(delta - 5_184_000) < 2


async def test_redirect_expired_url_returns_410(client: AsyncClient, app_state: AppState) -> None:

    from src.core.base62 import encode
    from src.core.snowflake import SnowflakeGenerator

    gen = SnowflakeGenerator(node_id=0)
    snowflake_id = gen.next_id()
    code = encode(snowflake_id)

    async with app_state.session_factory() as session:
        session.add(Url(
            id=snowflake_id,
            original_url="https://expired.example.com",
            is_blocked=False,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        ))
        await session.commit()

    response = await client.get(f"/{code}", follow_redirects=False)
    assert response.status_code == 410
    assert response.json() == {"detail": "This short link has expired"}


async def test_cache_ttl_set_on_creation(client: AsyncClient, app_state: AppState) -> None:
    response = await client.post(
        "/Create-URL",
        json={"url": "https://example.com/cache-ttl"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 201

    cache = app_state.cache
    assert isinstance(cache, FakeCacheForExpirationTest)
    assert len(cache.set_calls) >= 1
    _, _, ttl = cache.set_calls[0]
    assert ttl == 5_184_000


async def test_cleanup_worker_deletes_expired(client: AsyncClient, app_state: AppState) -> None:

    from sqlalchemy import select

    from src.infra.db.repository import SqlAlchemyUrlRepository

    async with app_state.session_factory() as session:
        session.add(Url(
            id=10,
            original_url="https://expired1.example.com",
            is_blocked=False,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        ))
        session.add(Url(
            id=20,
            original_url="https://expired2.example.com",
            is_blocked=False,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        ))
        session.add(Url(
            id=30,
            original_url="https://still.valid.example.com",
            is_blocked=False,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        ))
        await session.commit()

    async with app_state.session_factory() as session:
        repo = SqlAlchemyUrlRepository(session)
        await repo.delete_expired()

    async with app_state.session_factory() as session:
        result = await session.execute(select(Url))
        rows = list(result.scalars())
    assert len(rows) == 1
    assert rows[0].id == 30
    assert rows[0].original_url == "https://still.valid.example.com"


async def test_collision_reuses_expired_code(client: AsyncClient, app_state: AppState) -> None:

    from sqlalchemy import select

    from src.core.usecases.create_short_url import CreateShortURL
    from src.infra.db.repository import SqlAlchemyUrlRepository

    target_id = 99_999_999

    async with app_state.session_factory() as session:
        session.add(Url(
            id=target_id,
            original_url="https://old-expired.example.com",
            is_blocked=False,
            expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        ))
        await session.commit()

    class FixedIdGenerator:
        def next_id(self) -> int:
            return target_id

    async with app_state.session_factory() as session:
        repo = SqlAlchemyUrlRepository(session)
        use_case = CreateShortURL(
            id_generator=FixedIdGenerator(),
            repository=repo,
            base_url="https://sho.rt",
            cache=app_state.cache,
        )
        short_url = await use_case.execute("https://new.example.com", created_by="test@test.com")

    assert short_url.startswith("https://sho.rt/")

    async with app_state.session_factory() as session:
        result = await session.execute(select(Url).where(Url.id == target_id))
        row = result.scalar_one_or_none()
    assert row is not None
    assert row.original_url == "https://new.example.com"
    assert row.expires_at.replace(tzinfo=UTC) > datetime.now(UTC)
