from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import AppState, set_app_state
from src.api.main import create_app
from src.infra.config import Settings
from src.infra.db.models import Base, Url


class FakeRedisCache:
    """In-memory cache for testing rate limiting without a real Redis server."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._counters: dict[str, int] = {}
        self._fail: bool = False

    def set_fail(self, fail: bool) -> None:
        self._fail = fail

    async def get(self, key: str) -> str | None:
        if self._fail:
            return None
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int) -> None:
        if self._fail:
            return
        self._store[key] = value

    async def incr(self, key: str) -> int | None:
        if self._fail:
            return None
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key: str, ttl: int) -> None:
        pass

    async def aclose(self) -> None:
        pass

    async def close(self) -> None:
        await self.aclose()


AUTH_HEADER = {"X-Authenticated-User": "test@test.com"}


@pytest_asyncio.fixture
async def app_state() -> AsyncIterator[AppState]:
    test_db = "sqlite+aiosqlite:///:memory:"
    settings = Settings(
        database_url=test_db,
        short_base_url="https://sho.rt",
        snowflake_node_id=0,
        rate_limit_create_count=5,
        rate_limit_create_window_seconds=3600,
        rate_limit_redirect_count=5,
        rate_limit_redirect_window_seconds=60,
    )
    fake_cache = FakeRedisCache()
    state = AppState(settings, cache=fake_cache)
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


async def _insert_url(state: AppState, url_id: int, original_url: str) -> None:
    from datetime import UTC, datetime, timedelta
    row = Url(
        id=url_id,
        original_url=original_url,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=60),
    )
    async with state.session_factory() as session:
        session.add(row)
        await session.commit()


# ── 6.1 CreateURL: within limit (201) and exceeding limit (429) ──

async def test_create_url_within_limit_returns_201(client: AsyncClient, app_state: AppState) -> None:
    for _ in range(5):
        response = await client.post(
            "/Create-URL",
            json={"url": "https://www.example.com"},
            headers=AUTH_HEADER,
        )
        assert response.status_code == 201


async def test_create_url_exceeding_limit_returns_429(client: AsyncClient, app_state: AppState) -> None:
    for _ in range(5):
        await client.post(
            "/Create-URL",
            json={"url": "https://www.example.com"},
            headers=AUTH_HEADER,
        )
    response = await client.post(
        "/Create-URL",
        json={"url": "https://www.example.com/extra"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 429
    body = response.json()
    assert "Rate limit exceeded" in body["detail"]
    assert "Retry-After" in response.headers


# ── 6.2 CreateURL: window boundary resets counter ──

async def test_create_url_window_boundary_resets_counter(
    client: AsyncClient, app_state: AppState, mocker
) -> None:
    fake = app_state.cache
    # reach limit
    for _ in range(5):
        await client.post("/Create-URL", json={"url": "https://www.example.com"}, headers=AUTH_HEADER)
    # not exceeded yet
    resp = await client.post("/Create-URL", json={"url": "https://www.example.com/next"}, headers=AUTH_HEADER)
    assert resp.status_code == 429

    # simulate new window by resetting the fake counter store
    fake._counters.clear()

    resp = await client.post("/Create-URL", json={"url": "https://www.example.com/new-window"}, headers=AUTH_HEADER)
    assert resp.status_code == 201


# ── 6.3 CreateURL: fail-open when Redis is down ──

async def test_create_url_fail_open_when_cache_fails(client: AsyncClient, app_state: AppState) -> None:
    fake = app_state.cache
    fake.set_fail(True)
    response = await client.post(
        "/Create-URL",
        json={"url": "https://www.example.com"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 201


# ── 6.4 CreateURL: without auth still returns 403, not 429 ──

async def test_create_url_no_auth_returns_403_not_429(client: AsyncClient) -> None:
    response = await client.post(
        "/Create-URL",
        json={"url": "https://www.example.com"},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


# ── 6.5 Redirect: within limit resolves normally ──

async def test_redirect_within_limit_resolves(client: AsyncClient, app_state: AppState) -> None:
    from src.core import base62
    url_id = 1001
    code = base62.encode(url_id)
    await _insert_url(app_state, url_id, "https://www.example.com/target")

    for _ in range(5):
        response = await client.get(f"/{code}")
        assert response.status_code == 302


# ── 6.6 Redirect: exceeding limit returns 429 ──

async def test_redirect_exceeding_limit_returns_429(client: AsyncClient, app_state: AppState) -> None:
    from src.core import base62
    url_id = 2001
    code = base62.encode(url_id)
    await _insert_url(app_state, url_id, "https://www.example.com/target")

    for _ in range(5):
        await client.get(f"/{code}")
    response = await client.get(f"/{code}")
    assert response.status_code == 429
    assert "Retry-After" in response.headers


# ── 6.7 Redirect: fail-open when Redis is down ──

async def test_redirect_fail_open_when_cache_fails(client: AsyncClient, app_state: AppState) -> None:
    from src.core import base62
    url_id = 3001
    code = base62.encode(url_id)
    await _insert_url(app_state, url_id, "https://www.example.com/target")

    fake = app_state.cache
    fake.set_fail(True)

    response = await client.get(f"/{code}")
    assert response.status_code == 302


# ── 6.8 Redirect: different IPs have independent counters ──

async def test_redirect_different_ips_independent_counters(
    client: AsyncClient, app_state: AppState
) -> None:
    from src.core import base62
    url_id = 4001
    code = base62.encode(url_id)
    await _insert_url(app_state, url_id, "https://www.example.com/target")

    # Exhaust limit for one IP
    for _ in range(5):
        await client.get(f"/{code}", headers={"X-Forwarded-For": "10.0.0.1"})
    resp = await client.get(f"/{code}", headers={"X-Forwarded-For": "10.0.0.1"})
    assert resp.status_code == 429

    # Different IP should still be allowed
    resp = await client.get(f"/{code}", headers={"X-Forwarded-For": "10.0.0.2"})
    assert resp.status_code == 302


# ── 6.9 Verify Retry-After header in 429 responses ──

async def test_429_response_has_retry_after_header(client: AsyncClient, app_state: AppState) -> None:
    for _ in range(5):
        await client.post(
            "/Create-URL",
            json={"url": "https://www.example.com"},
            headers=AUTH_HEADER,
        )
    response = await client.post(
        "/Create-URL",
        json={"url": "https://www.example.com/extra"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 429
    retry_after = response.headers.get("Retry-After")
    assert retry_after is not None
    assert int(retry_after) > 0
