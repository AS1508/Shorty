from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.dependencies import AppState, get_app_state, set_app_state
from src.api.routes import my_urls, redirect, shortener
from src.core.expiration import CLEANUP_INTERVAL_SECONDS, SOFT_DELETE_PURGE_DAYS
from src.infra.db.repository import SqlAlchemyUrlRepository

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = get_app_state()
    app.state.app_state = state
    cleanup_task = asyncio.create_task(_run_cleanup_loop(state))
    try:
        yield
    finally:
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task
        await state.dispose()
        set_app_state(None)


async def _run_cleanup_loop(state: AppState) -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            async with state.session_factory() as session:
                repo = SqlAlchemyUrlRepository(session)
                await repo.delete_expired()
        except Exception:
            logger.warning("expired cleanup cycle failed", exc_info=True)

        try:
            async with state.session_factory() as session:
                repo = SqlAlchemyUrlRepository(session)
                await repo.delete_soft_deleted_older_than(SOFT_DELETE_PURGE_DAYS)
        except Exception:
            logger.warning("soft-deleted cleanup cycle failed", exc_info=True)


def create_app(state: AppState | None = None) -> FastAPI:
    if state is not None:
        set_app_state(state)
    app = FastAPI(title="Shorty", version="0.1.0", lifespan=lifespan)
    app.include_router(shortener.router)
    app.include_router(redirect.router)
    app.include_router(my_urls.router)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {"msg": "invalid request"}
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": first.get("msg", "invalid request")},
        )

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000)
