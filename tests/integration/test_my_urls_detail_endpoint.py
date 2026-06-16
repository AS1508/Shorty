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
        )
        session.add(row)
        await session.commit()


async def test_detail_own_url_returns_200(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, original_url="https://own.example.com")

    response = await client.get(f"/my-urls/{code}", headers=AUTH_HEADER)

    assert response.status_code == 200
    body = response.json()
    assert body["short_code"] == code
    assert body["short_url"] == f"https://sho.rt/{code}"
    assert body["original_url"] == "https://own.example.com"
    assert body["is_expired"] is False
    assert body["is_blocked"] is False
    assert body["deleted_at"] is None
    assert "created_at" in body
    assert "expires_at" in body


async def test_detail_other_users_url_returns_404(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, created_by="other@test.com")

    response = await client.get(f"/my-urls/{code}", headers=AUTH_HEADER)

    assert response.status_code == 404


async def test_detail_nonexistent_url_returns_404(
    client: AsyncClient, app_state: AppState
) -> None:
    code = encode(9999)
    response = await client.get(f"/my-urls/{code}", headers=AUTH_HEADER)
    assert response.status_code == 404


async def test_detail_invalid_short_code_returns_400(
    client: AsyncClient, app_state: AppState
) -> None:
    response = await client.get("/my-urls/!!!invalid", headers=AUTH_HEADER)
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


async def test_detail_unauthenticated_returns_403(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    response = await client.get(f"/my-urls/{code}")

    assert response.status_code == 403


async def test_detail_expired_url_shows_is_expired(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(
        app_state, sid,
        original_url="https://expired.example.com",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    response = await client.get(f"/my-urls/{code}", headers=AUTH_HEADER)

    assert response.status_code == 200
    body = response.json()
    assert body["is_expired"] is True


async def test_detail_blocked_url_shows_is_blocked(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, is_blocked=True)

    response = await client.get(f"/my-urls/{code}", headers=AUTH_HEADER)

    assert response.status_code == 200
    body = response.json()
    assert body["is_blocked"] is True


async def test_detail_deleted_url_shows_deleted_at(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, deleted_at=datetime.now(UTC))

    response = await client.get(f"/my-urls/{code}", headers=AUTH_HEADER)

    assert response.status_code == 200
    body = response.json()
    assert body["deleted_at"] is not None
