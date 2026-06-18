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
            expires_at=now + timedelta(days=60),
        )
        session.add(row)
        await session.commit()


async def test_admin_blocks_url(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    response = await client.post(f"/admin/block/{code}", headers=ADMIN_AUTH)

    assert response.status_code == 200
    assert response.json() == {"status": "blocked"}


async def test_admin_blocks_url_returns_403_on_redirect(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    await client.post(f"/admin/block/{code}", headers=ADMIN_AUTH)
    redirect_resp = await client.get(f"/{code}")
    assert redirect_resp.status_code == 403


async def test_admin_unblocks_url(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, is_blocked=True)

    response = await client.post(f"/admin/unblock/{code}", headers=ADMIN_AUTH)

    assert response.status_code == 200
    assert response.json() == {"status": "unblocked"}


async def test_admin_unblocks_url_restores_redirect(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, is_blocked=True)

    await client.post(f"/admin/unblock/{code}", headers=ADMIN_AUTH)
    redirect_resp = await client.get(f"/{code}")
    assert redirect_resp.status_code == 302


async def test_block_nonexistent_url_returns_404(
    client: AsyncClient, app_state: AppState
) -> None:
    response = await client.post(f"/admin/block/{encode(99)}", headers=ADMIN_AUTH)
    assert response.status_code == 404


async def test_non_admin_cannot_block(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    await _insert_url(app_state, sid)

    response = await client.post(f"/admin/block/{encode(sid)}", headers=USER_AUTH)
    assert response.status_code == 403


async def test_non_admin_cannot_unblock(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    await _insert_url(app_state, sid)

    response = await client.post(f"/admin/unblock/{encode(sid)}", headers=USER_AUTH)
    assert response.status_code == 403


async def test_non_admin_cannot_list_all_urls(
    client: AsyncClient, app_state: AppState
) -> None:
    response = await client.get("/admin/urls", headers=USER_AUTH)
    assert response.status_code == 403


async def test_unauthenticated_cannot_access_admin(
    client: AsyncClient, app_state: AppState
) -> None:
    response = await client.get("/admin/urls")
    assert response.status_code == 403


async def test_admin_lists_all_urls(
    client: AsyncClient, app_state: AppState
) -> None:
    await _insert_url(app_state, 100, created_by="alice@a.com")
    await _insert_url(app_state, 200, created_by="bob@b.com")

    response = await client.get("/admin/urls", headers=ADMIN_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert len(body["urls"]) == 2
    owners = {u["created_by"] for u in body["urls"]}
    assert owners == {"alice@a.com", "bob@b.com"}


async def test_admin_list_supports_pagination(
    client: AsyncClient, app_state: AppState
) -> None:
    for i in (50, 40, 30):
        await _insert_url(app_state, i)

    page1 = await client.get("/admin/urls?limit=2", headers=ADMIN_AUTH)
    body = page1.json()
    assert len(body["urls"]) == 2
    assert body["has_more"] is True
    assert "next_cursor" in body

    page2 = await client.get(
        f"/admin/urls?cursor={body['next_cursor']}&limit=2", headers=ADMIN_AUTH
    )
    body2 = page2.json()
    assert len(body2["urls"]) == 1
    assert body2["has_more"] is False


async def test_block_invalidates_cache(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    app_state.cache._store[str(sid)] = '{"s":"ok","u":"https://example.com/42"}'  # type: ignore[attr-defined]

    await client.post(f"/admin/block/{code}", headers=ADMIN_AUTH)

    assert str(sid) not in app_state.cache._store  # type: ignore[attr-defined]
