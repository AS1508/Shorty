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

AUTH_HEADER = {"X-Authenticated-User": "test@test.com"}


class FakeCacheForTest:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:  # noqa: ARG002
        self._store[key] = value

    async def incr(self, key: str) -> int | None:  # noqa: ARG002
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
    state.cache = FakeCacheForTest()
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


async def _insert_url(
    state: AppState,
    snowflake_id: int,
    *,
    original_url: str = "https://example.com",
    created_by: str = "test@test.com",
    is_blocked: bool = False,
    deleted_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> None:
    now = datetime.now(UTC)
    async with state.session_factory() as session:
        row = Url(
            id=snowflake_id,
            original_url=original_url,
            created_by=created_by,
            is_blocked=is_blocked,
            created_at=now,
            expires_at=expires_at or (now + timedelta(days=60)),
            deleted_at=deleted_at,
        )
        session.add(row)
        await session.commit()


async def _get_url(state: AppState, snowflake_id: int) -> Url | None:
    async with state.session_factory() as session:
        result = await session.execute(select(Url).where(Url.id == snowflake_id))
        return result.scalar_one_or_none()


async def test_delete_own_url_returns_204_and_marks_deleted_at(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    response = await client.delete(f"/my-urls/{code}", headers=AUTH_HEADER)

    assert response.status_code == 204
    assert response.content == b""
    row = await _get_url(app_state, sid)
    assert row is not None
    assert row.deleted_at is not None


async def test_delete_others_url_returns_404(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, created_by="other@test.com")

    response = await client.delete(f"/my-urls/{code}", headers=AUTH_HEADER)

    assert response.status_code == 404
    row = await _get_url(app_state, sid)
    assert row is not None
    assert row.deleted_at is None


async def test_delete_nonexistent_url_returns_404(
    client: AsyncClient, app_state: AppState
) -> None:
    code = encode(9999)
    response = await client.delete(f"/my-urls/{code}", headers=AUTH_HEADER)
    assert response.status_code == 404


async def test_delete_already_deleted_returns_404(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, deleted_at=datetime.now(UTC))

    response = await client.delete(f"/my-urls/{code}", headers=AUTH_HEADER)
    assert response.status_code == 404


async def test_delete_without_auth_returns_403(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    response = await client.delete(f"/my-urls/{code}")

    assert response.status_code == 403


async def test_delete_with_invalid_short_code_returns_400(
    client: AsyncClient, app_state: AppState
) -> None:
    response = await client.delete("/my-urls/!!!invalid", headers=AUTH_HEADER)
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


async def test_delete_invalidates_cache_and_redirect_returns_410(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    # Pre-populate cache with a positive entry
    app_state.cache._store[str(sid)] = '{"s":"ok","u":"https://example.com"}'  # type: ignore[attr-defined]

    await client.delete(f"/my-urls/{code}", headers=AUTH_HEADER)

    # Cache should be evicted
    assert str(sid) not in app_state.cache._store  # type: ignore[attr-defined]

    # Redirect should return 410
    redirect_response = await client.get(f"/{code}")
    assert redirect_response.status_code == 410


async def test_deleted_url_returns_410_on_redirect(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, deleted_at=datetime.now(UTC))

    response = await client.get(f"/{code}")
    assert response.status_code == 410


async def test_delete_blocked_url_succeeds(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid, is_blocked=True)

    response = await client.delete(f"/my-urls/{code}", headers=AUTH_HEADER)

    assert response.status_code == 204
    row = await _get_url(app_state, sid)
    assert row is not None
    assert row.deleted_at is not None


async def test_delete_expired_url_succeeds(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(
        app_state,
        sid,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    response = await client.delete(f"/my-urls/{code}", headers=AUTH_HEADER)

    assert response.status_code == 204
    row = await _get_url(app_state, sid)
    assert row is not None
    assert row.deleted_at is not None


async def test_concurrent_deletes_one_succeeds(
    client: AsyncClient, app_state: AppState
) -> None:
    sid = 42
    code = encode(sid)
    await _insert_url(app_state, sid)

    async with (
        AsyncClient(transport=ASGITransport(app=create_app(state=app_state)), base_url="http://test") as c1,
        AsyncClient(transport=ASGITransport(app=create_app(state=app_state)), base_url="http://test") as c2,
    ):
        r1, r2 = await asyncio.gather(
            c1.delete(f"/my-urls/{code}", headers=AUTH_HEADER),
            c2.delete(f"/my-urls/{code}", headers=AUTH_HEADER),
        )

    statuses = {r1.status_code, r2.status_code}
    assert statuses == {204, 404}
    row = await _get_url(app_state, sid)
    assert row is not None
    assert row.deleted_at is not None


async def test_cleanup_worker_purges_old_soft_deleted(
    app_state: AppState,
) -> None:
    sid = 42
    thirty_one_days_ago = datetime.now(UTC) - timedelta(days=31)
    await _insert_url(app_state, sid, deleted_at=thirty_one_days_ago)

    from src.core.expiration import SOFT_DELETE_PURGE_DAYS
    from src.infra.db.repository import SqlAlchemyUrlRepository

    async with app_state.session_factory() as session:
        repo = SqlAlchemyUrlRepository(session)
        await repo.delete_soft_deleted_older_than(SOFT_DELETE_PURGE_DAYS)

    row = await _get_url(app_state, sid)
    assert row is None


async def test_cleanup_worker_keeps_recent_soft_deleted(
    app_state: AppState,
) -> None:
    sid = 42
    five_days_ago = datetime.now(UTC) - timedelta(days=5)
    await _insert_url(app_state, sid, deleted_at=five_days_ago)

    from src.core.expiration import SOFT_DELETE_PURGE_DAYS
    from src.infra.db.repository import SqlAlchemyUrlRepository

    async with app_state.session_factory() as session:
        repo = SqlAlchemyUrlRepository(session)
        await repo.delete_soft_deleted_older_than(SOFT_DELETE_PURGE_DAYS)

    row = await _get_url(app_state, sid)
    assert row is not None
    assert row.deleted_at is not None
