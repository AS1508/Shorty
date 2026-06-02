from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.snowflake import SnowflakeGenerator
from src.core.usecases.create_short_url import CreateShortURL
from src.infra.config import Settings, get_settings
from src.infra.db.repository import SqlAlchemyUrlRepository


class AppState:
    """Application-scoped singletons built once at startup."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.engine = create_async_engine(self.settings.database_url, future=True)
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            autoflush=False,
        )
        self.id_generator = SnowflakeGenerator(node_id=self.settings.snowflake_node_id)

    async def dispose(self) -> None:
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
    )


CreateShortURLDep = Annotated[CreateShortURL, Depends(get_use_case)]
