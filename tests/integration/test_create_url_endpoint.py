from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.dependencies import AppState, set_app_state
from src.api.main import create_app
from src.infra.config import Settings
from src.infra.db.models import Base, Url


@pytest_asyncio.fixture
async def app_state() -> AsyncIterator[AppState]:
    test_db = "sqlite+aiosqlite:///:memory:"
    settings = Settings(
        database_url=test_db,
        short_base_url="https://sho.rt",
        snowflake_node_id=0,
    )
    state = AppState(settings)
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


async def _query_persisted_url(state: AppState, url_id: int) -> Url | None:
    async with state.session_factory() as session:
        result = await session.execute(select(Url).where(Url.id == url_id))
        return result.scalar_one_or_none()


async def test_valid_url_returns_201_and_persists_row(client: AsyncClient, app_state: AppState) -> None:
    response = await client.post(
        "/Create-URL",
        json={"url": "https://www.example.com/some/long/path"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "short_url" in body
    assert body["short_url"].startswith("https://sho.rt/")
    code = body["short_url"].rsplit("/", 1)[-1]
    assert code.isalnum()

    persisted = await _query_persisted_url(app_state, 0)
    # snowflake IDs from the in-memory clock start near epoch+something; we just want to confirm
    # at least one row was written with the right original URL.
    async with app_state.session_factory() as session:
        result = await session.execute(select(Url))
        rows = list(result.scalars())
    assert len(rows) == 1
    assert rows[0].original_url == "https://www.example.com/some/long/path"
    _ = persisted


async def test_missing_url_field_returns_400(client: AsyncClient) -> None:
    response = await client.post("/Create-URL", json={})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


async def test_non_string_url_returns_400(client: AsyncClient) -> None:
    response = await client.post("/Create-URL", json={"url": 123})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


async def test_url_without_scheme_returns_400(client: AsyncClient) -> None:
    response = await client.post("/Create-URL", json={"url": "example.com/path"})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


async def test_oversize_url_returns_400(client: AsyncClient) -> None:
    long_path = "x" * 2_100
    response = await client.post(
        "/Create-URL",
        json={"url": f"https://example.com/{long_path}"},
    )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body
