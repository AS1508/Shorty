from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import AppState, set_app_state
from src.api.main import create_app
from src.core.base62 import encode
from src.infra.config import Settings
from src.infra.db.models import Base, Url

AUTH_HEADER = {"X-Authenticated-User": "test@test.com"}


class FakeCacheForTest:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:  # noqa: ARG002
        self._store[key] = value

    async def incr(self, key: str) -> int | None:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key: str, ttl: int) -> None:  # noqa: ARG002
        pass

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def aclose(self) -> None:
        pass

    async def close(self) -> None:
        await self.aclose()


@pytest_asyncio.fixture
async def app_state() -> AsyncIterator[AppState]:
    test_db = "sqlite+aiosqlite:///:memory:"
    settings = Settings(
        database_url=test_db,
        short_base_url="https://sho.rt",
        snowflake_node_id=0,
        rate_limit_my_urls_count=100,
        rate_limit_my_urls_window_seconds=3600,
    )
    state = AppState(settings, cache=FakeCacheForTest())
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


async def _insert_url(
    state: AppState,
    snowflake_id: int,
    *,
    original_url: str | None = None,
    created_by: str = "test@test.com",
    deleted_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> None:
    now = datetime.now(UTC)
    url = original_url or f"https://example.com/{snowflake_id}"
    async with state.session_factory() as session:
        row = Url(
            id=snowflake_id,
            original_url=url,
            created_by=created_by,
            created_at=now - timedelta(seconds=snowflake_id),
            expires_at=expires_at or (now + timedelta(days=60)),
            deleted_at=deleted_at,
        )
        session.add(row)
        await session.commit()


async def test_list_empty_when_no_urls(
    client: AsyncClient, app_state: AppState
) -> None:
    response = await client.get("/my-urls", headers=AUTH_HEADER)

    assert response.status_code == 200
    body = response.json()
    assert body["urls"] == []
    assert body["has_more"] is False
    assert "next_cursor" not in body


async def test_list_returns_own_urls(
    client: AsyncClient, app_state: AppState
) -> None:
    await _insert_url(app_state, 100, original_url="https://a.example.com")
    await _insert_url(app_state, 200, original_url="https://b.example.com")
    await _insert_url(app_state, 300, original_url="https://c.example.com")

    response = await client.get("/my-urls", headers=AUTH_HEADER)

    assert response.status_code == 200
    body = response.json()
    assert len(body["urls"]) == 3
    assert body["has_more"] is False
    assert body["urls"][0]["original_url"] == "https://c.example.com"  # newest first
    assert body["urls"][1]["original_url"] == "https://b.example.com"
    assert body["urls"][2]["original_url"] == "https://a.example.com"
    for item in body["urls"]:
        assert "short_code" in item
        assert item["short_url"].startswith("https://sho.rt/")
        assert item["short_code"] == item["short_url"].rsplit("/", 1)[-1]
        assert isinstance(item["is_expired"], bool)
        assert isinstance(item["is_blocked"], bool)
        assert "created_at" in item
        assert "expires_at" in item


async def test_list_pagination(
    client: AsyncClient, app_state: AppState
) -> None:
    for i in (50, 40, 30, 20, 10):
        await _insert_url(app_state, i)

    page1 = await client.get("/my-urls?limit=3", headers=AUTH_HEADER)
    assert page1.status_code == 200
    body = page1.json()
    assert len(body["urls"]) == 3
    assert body["has_more"] is True
    assert "next_cursor" in body
    assert [u["short_url"].rsplit("/", 1)[-1] for u in body["urls"]] == [
        encode(50), encode(40), encode(30)
    ]

    cursor = body["next_cursor"]
    page2 = await client.get(f"/my-urls?cursor={cursor}&limit=3", headers=AUTH_HEADER)
    assert page2.status_code == 200
    body2 = page2.json()
    assert len(body2["urls"]) == 2
    assert body2["has_more"] is False
    assert [u["short_url"].rsplit("/", 1)[-1] for u in body2["urls"]] == [
        encode(20), encode(10)
    ]


async def test_list_only_shows_own_urls(
    client: AsyncClient, app_state: AppState
) -> None:
    await _insert_url(app_state, 1, created_by="alice@a.com")
    await _insert_url(app_state, 2, created_by="test@test.com")
    await _insert_url(app_state, 3, created_by="alice@a.com")

    response = await client.get("/my-urls", headers=AUTH_HEADER)

    assert response.status_code == 200
    body = response.json()
    assert len(body["urls"]) == 1
    assert body["urls"][0]["short_code"] == encode(2)


async def test_list_unauthenticated_returns_403(
    client: AsyncClient, app_state: AppState
) -> None:
    response = await client.get("/my-urls")
    assert response.status_code == 403


async def test_list_includes_expired_url(
    client: AsyncClient, app_state: AppState
) -> None:
    await _insert_url(
        app_state, 42,
        original_url="https://expired.example.com",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    response = await client.get("/my-urls", headers=AUTH_HEADER)

    assert response.status_code == 200
    body = response.json()
    assert len(body["urls"]) == 1
    assert body["urls"][0]["is_expired"] is True


async def test_list_includes_deleted_url(
    client: AsyncClient, app_state: AppState
) -> None:
    await _insert_url(
        app_state, 42,
        original_url="https://deleted.example.com",
        deleted_at=datetime.now(UTC),
    )

    response = await client.get("/my-urls", headers=AUTH_HEADER)

    assert response.status_code == 200
    body = response.json()
    assert len(body["urls"]) == 1
    assert body["urls"][0]["deleted_at"] is not None


async def test_list_invalid_cursor_returns_400(
    client: AsyncClient, app_state: AppState
) -> None:
    response = await client.get("/my-urls?cursor=abc", headers=AUTH_HEADER)
    assert response.status_code == 400


async def test_list_limit_clamped(
    client: AsyncClient, app_state: AppState
) -> None:
    for i in (100, 99, 98, 97, 96):
        await _insert_url(app_state, i)

    response = await client.get("/my-urls?limit=1", headers=AUTH_HEADER)
    assert response.status_code == 200
    body = response.json()
    assert len(body["urls"]) == 1

    response2 = await client.get("/my-urls?limit=200", headers=AUTH_HEADER)
    assert response2.status_code == 200
    body2 = response2.json()
    assert len(body2["urls"]) == 5  # all 5, capped by max_limit internally
