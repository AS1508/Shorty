from __future__ import annotations

import base64
import hmac
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.ports import CachePort
from src.core.rate_limit import FixedWindowRateLimiter
from src.core.snowflake import SnowflakeGenerator
from src.core.usecases.create_short_url import CreateShortURL
from src.core.usecases.resolve_url import ResolveURL
from src.infra.cache.redis import RedisCache
from src.infra.config import Settings, get_settings
from src.infra.db.repository import SqlAlchemyUrlRepository


class AppState:
    """Application-scoped singletons built once at startup."""

    def __init__(self, settings: Settings | None = None, cache: CachePort | None = None) -> None:
        self.settings = settings or get_settings()
        self.engine = create_async_engine(self.settings.database_url, future=True)
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            autoflush=False,
        )
        self.id_generator = SnowflakeGenerator(node_id=self.settings.snowflake_node_id)
        self.cache = cache if cache is not None else RedisCache(self.settings.redis_url)

    async def dispose(self) -> None:
        await self.cache.aclose()
        await self.engine.dispose()


_app_state: AppState | None = None


def get_app_state() -> AppState:
    global _app_state
    if _app_state is None:
        _app_state = AppState()
    return _app_state


def set_app_state(state: AppState | None) -> None:
    """Test hook to inject a custom app state (e.g., with a SQLite engine)."""
    global _app_state
    _app_state = state


AppStateDep = Annotated[AppState, Depends(get_app_state)]


async def get_session(state: AppStateDep) -> AsyncIterator[AsyncSession]:
    async with state.session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_repository(session: SessionDep) -> SqlAlchemyUrlRepository:
    return SqlAlchemyUrlRepository(session)


RepositoryDep = Annotated[SqlAlchemyUrlRepository, Depends(get_repository)]


def get_use_case(state: AppStateDep, repository: RepositoryDep) -> CreateShortURL:
    return CreateShortURL(
        id_generator=state.id_generator,
        repository=repository,
        base_url=state.settings.short_base_url,
        cache=state.cache,
    )


CreateShortURLDep = Annotated[CreateShortURL, Depends(get_use_case)]


def get_resolve_use_case(state: AppStateDep, repository: RepositoryDep) -> ResolveURL:
    return ResolveURL(repository=repository, cache=state.cache)


ResolveURLDep = Annotated[ResolveURL, Depends(get_resolve_use_case)]


def get_settings_dep(state: AppStateDep) -> Settings:
    return state.settings


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def require_authenticated_user(
    request: Request,
    settings: SettingsDep,
) -> str:
    email = request.headers.get("X-Authenticated-User", "").strip()

    if not email or "@" not in email or len(email) > 254:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if settings.proxy_shared_secret:
        signature = request.headers.get("X-Auth-Signature", "").strip()
        expected = base64.b64encode(
            hmac.new(
                settings.proxy_shared_secret.encode(),
                email.encode(),
                "sha256",
            ).digest()
        ).decode()
        if not signature or not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return email


AuthenticatedUserDep = Annotated[str, Depends(require_authenticated_user)]


async def require_rate_limit_create(
    state: AppStateDep,
    request: Request,
    authenticated_user: AuthenticatedUserDep,
) -> None:
    limiter = FixedWindowRateLimiter(
        cache=state.cache,
        key_prefix="rate:create",
        limit=state.settings.rate_limit_create_count,
        window_seconds=state.settings.rate_limit_create_window_seconds,
    )
    result = await limiter.check(authenticated_user)
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {result.retry_after_seconds} seconds.",
            headers={"Retry-After": str(result.retry_after_seconds)},
        )


RateLimitCreateDep = Annotated[None, Depends(require_rate_limit_create)]


async def require_rate_limit_redirect(
    state: AppStateDep,
    request: Request,
) -> None:
    ip = FixedWindowRateLimiter.extract_client_ip(
        forwarded=request.headers.get("X-Forwarded-For"),
        client_host=request.client.host if request.client else None,
    )
    limiter = FixedWindowRateLimiter(
        cache=state.cache,
        key_prefix="rate:redirect",
        limit=state.settings.rate_limit_redirect_count,
        window_seconds=state.settings.rate_limit_redirect_window_seconds,
    )
    result = await limiter.check(ip)
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {result.retry_after_seconds} seconds.",
            headers={"Retry-After": str(result.retry_after_seconds)},
        )


RateLimitRedirectDep = Annotated[None, Depends(require_rate_limit_redirect)]
