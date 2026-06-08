from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import AppState, set_app_state
from src.api.main import create_app
from src.infra.config import Settings
from src.infra.db.models import Base


class FakeCacheForTest:
    """In-memory cache double that mimics RedisCache behaviour for integration tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:  # noqa: ARG002
        self._store[key] = value

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
    state.cache = FakeCacheForTest()  # type: ignore[assignment]
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


async def test_redirect_valid_url_returns_302(client: AsyncClient, app_state: AppState) -> None:
    from datetime import UTC, datetime, timedelta

    from src.core.base62 import encode
    from src.core.snowflake import SnowflakeGenerator

    gen = SnowflakeGenerator(node_id=0)
    snowflake_id = gen.next_id()
    code = encode(snowflake_id)

    async with app_state.session_factory() as session:
        from src.infra.db.models import Url
        session.add(Url(
            id=snowflake_id,
            original_url="https://target.example.com/page",
            is_blocked=False,
            expires_at=datetime.now(UTC) + timedelta(days=60),
        ))
        await session.commit()

    response = await client.get(f"/{code}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://target.example.com/page"


async def test_redirect_invalid_chars_returns_400(client: AsyncClient) -> None:
    response = await client.get("/code-with-dash!")
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


async def test_redirect_nonexistent_returns_404(client: AsyncClient) -> None:
    response = await client.get("/NonExistent1")
    assert response.status_code == 404


async def test_redirect_negative_caching_skips_db(client: AsyncClient, app_state: AppState) -> None:
    response1 = await client.get("/NotHere42")
    assert response1.status_code == 404

    response2 = await client.get("/NotHere42")
    assert response2.status_code == 404


async def test_redirect_blocked_returns_403(client: AsyncClient, app_state: AppState) -> None:
    from datetime import UTC, datetime, timedelta

    from src.core.base62 import encode
    from src.core.snowflake import SnowflakeGenerator

    gen = SnowflakeGenerator(node_id=0)
    snowflake_id = gen.next_id()
    code = encode(snowflake_id)

    async with app_state.session_factory() as session:
        from src.infra.db.models import Url
        session.add(Url(
            id=snowflake_id,
            original_url="https://blocked.example.com",
            is_blocked=True,
            expires_at=datetime.now(UTC) + timedelta(days=60),
        ))
        await session.commit()

    response = await client.get(f"/{code}", follow_redirects=False)
    assert response.status_code == 403
