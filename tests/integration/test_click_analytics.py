from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.dependencies import AppState, set_app_state
from src.api.main import create_app
from src.core.base62 import encode
from src.infra.config import Settings
from src.infra.db.models import Base, Url

ADMIN_AUTH = {"X-Authenticated-User": "admin@test.com"}
USER_AUTH = {"X-Authenticated-User": "user@test.com"}


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
        admin_emails=frozenset({"admin@test.com"}),
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
    created_by: str = "user@test.com",
    is_blocked: bool = False,
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
            is_blocked=is_blocked,
            created_at=now,
            expires_at=expires_at or (now + timedelta(days=60)),
            deleted_at=deleted_at,
            clicks=0,
        )
        session.add(row)
        await session.commit()


async def _get_clicks(state: AppState, snowflake_id: int) -> int:
    async with state.session_factory() as session:
        result = await session.execute(select(Url).where(Url.id == snowflake_id))
        row = result.scalar_one_or_none()
        return row.clicks if row else 0


async def test_redirect_increments_clicks(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    for _ in range(3):
        await client.get(f"/{code}")

    assert await _get_clicks(app_state, sid) == 3


async def test_redirect_does_not_increment_on_blocked(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, is_blocked=True)

    await client.get(f"/{code}")
    assert await _get_clicks(app_state, sid) == 0


async def test_redirect_does_not_increment_on_expired(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, expires_at=datetime.now(UTC) - timedelta(days=1))

    await client.get(f"/{code}")
    assert await _get_clicks(app_state, sid) == 0


async def test_redirect_does_not_increment_on_deleted(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, deleted_at=datetime.now(UTC))

    await client.get(f"/{code}")
    assert await _get_clicks(app_state, sid) == 0


async def test_concurrent_clicks_counted_correctly(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    async def _click() -> None:
        transport = ASGITransport(app=create_app(state=app_state))
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            await c.get(f"/{code}")

    await asyncio.gather(*[_click() for _ in range(10)])

    assert await _get_clicks(app_state, sid) == 10


async def test_clicks_in_my_urls_list(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    await client.get(f"/{code}")
    await client.get(f"/{code}")

    response = await client.get("/my-urls", headers=USER_AUTH)
    body = response.json()
    assert body["urls"][0]["clicks"] == 2


async def test_clicks_in_my_urls_detail(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    await client.get(f"/{code}")

    response = await client.get(f"/my-urls/{code}", headers=USER_AUTH)
    assert response.json()["clicks"] == 1


async def test_clicks_in_admin_list(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    await _insert_url(app_state, sid)

    response = await client.get("/admin/urls", headers=ADMIN_AUTH)
    assert response.json()["urls"][0]["clicks"] == 0


async def test_admin_stats_endpoint(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, created_by="other@test.com")

    await client.get(f"/{code}")
    await client.get(f"/{code}")

    response = await client.get(f"/admin/stats/{code}", headers=ADMIN_AUTH)
    body = response.json()
    assert response.status_code == 200
    assert body["clicks"] == 2
    assert body["created_by"] == "other@test.com"


async def test_admin_stats_for_nonexistent_returns_404(
    client: AsyncClient, app_state: AppState
) -> None:
    response = await client.get(f"/admin/stats/{encode(99)}", headers=ADMIN_AUTH)
    assert response.status_code == 404


async def test_non_admin_stats_returns_403(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    response = await client.get(f"/admin/stats/{code}", headers=USER_AUTH)
    assert response.status_code == 403
