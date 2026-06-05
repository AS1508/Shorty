from __future__ import annotations

import base64
import hmac
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.dependencies import AppState, set_app_state
from src.api.main import create_app
from src.infra.config import Settings
from src.infra.db.models import Base, Url

AUTH_HEADER = {"X-Authenticated-User": "test@test.com"}


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
async def app_state_with_secret() -> AsyncIterator[AppState]:
    test_db = "sqlite+aiosqlite:///:memory:"
    settings = Settings(
        database_url=test_db,
        short_base_url="https://sho.rt",
        snowflake_node_id=0,
        proxy_shared_secret="test-secret",
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


@pytest_asyncio.fixture
async def client_with_secret(app_state_with_secret: AppState) -> AsyncIterator[AsyncClient]:
    app = create_app(state=app_state_with_secret)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _query_persisted_url(state: AppState, url_id: int) -> Url | None:
    async with state.session_factory() as session:
        result = await session.execute(select(Url).where(Url.id == url_id))
        return result.scalar_one_or_none()


# ── Happy path (updated with auth header) ────────────────────

async def test_valid_url_returns_201_and_persists_row(client: AsyncClient, app_state: AppState) -> None:
    response = await client.post(
        "/Create-URL",
        json={"url": "https://www.example.com/some/long/path"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 201
    body = response.json()
    assert "short_url" in body
    assert body["short_url"].startswith("https://sho.rt/")
    code = body["short_url"].rsplit("/", 1)[-1]
    assert code.isalnum()

    async with app_state.session_factory() as session:
        result = await session.execute(select(Url))
        rows = list(result.scalars())
    assert len(rows) == 1
    assert rows[0].original_url == "https://www.example.com/some/long/path"
    assert rows[0].created_by == "test@test.com"


async def test_valid_url_with_signature(client_with_secret: AsyncClient, app_state_with_secret: AppState) -> None:
    email = "dev@midominio.com"
    secret = "test-secret"
    sig = base64.b64encode(hmac.new(secret.encode(), email.encode(), "sha256").digest()).decode()
    response = await client_with_secret.post(
        "/Create-URL",
        json={"url": "https://www.example.com/some/long/path"},
        headers={"X-Authenticated-User": email, "X-Auth-Signature": sig},
    )
    assert response.status_code == 201


# ── Validation (unchanged behavior, just add auth header) ────

async def test_missing_url_field_returns_400(client: AsyncClient) -> None:
    response = await client.post("/Create-URL", json={}, headers=AUTH_HEADER)
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


async def test_non_string_url_returns_400(client: AsyncClient) -> None:
    response = await client.post("/Create-URL", json={"url": 123}, headers=AUTH_HEADER)
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


async def test_url_without_scheme_returns_400(client: AsyncClient) -> None:
    response = await client.post("/Create-URL", json={"url": "example.com/path"}, headers=AUTH_HEADER)
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


async def test_oversize_url_returns_400(client: AsyncClient) -> None:
    long_path = "x" * 2_100
    response = await client.post(
        "/Create-URL",
        json={"url": f"https://example.com/{long_path}"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


# ── Auth: missing / invalid header → 403 ─────────────────────

async def test_no_auth_header_returns_403(client: AsyncClient) -> None:
    response = await client.post(
        "/Create-URL",
        json={"url": "https://www.example.com/path"},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


async def test_empty_auth_header_returns_403(client: AsyncClient) -> None:
    response = await client.post(
        "/Create-URL",
        json={"url": "https://www.example.com/path"},
        headers={"X-Authenticated-User": ""},
    )
    assert response.status_code == 403


async def test_invalid_email_format_returns_403(client: AsyncClient) -> None:
    response = await client.post(
        "/Create-URL",
        json={"url": "https://www.example.com/path"},
        headers={"X-Authenticated-User": "not-an-email"},
    )
    assert response.status_code == 403


# ── HMAC signature tests (secret is set) ─────────────────────

async def test_missing_signature_returns_403(client_with_secret: AsyncClient) -> None:
    response = await client_with_secret.post(
        "/Create-URL",
        json={"url": "https://www.example.com/path"},
        headers={"X-Authenticated-User": "test@test.com"},
    )
    assert response.status_code == 403


async def test_wrong_signature_returns_403(client_with_secret: AsyncClient) -> None:
    response = await client_with_secret.post(
        "/Create-URL",
        json={"url": "https://www.example.com/path"},
        headers={
            "X-Authenticated-User": "test@test.com",
            "X-Auth-Signature": base64.b64encode(b"wrong").decode(),
        },
    )
    assert response.status_code == 403
