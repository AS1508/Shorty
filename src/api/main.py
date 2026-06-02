from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.dependencies import AppState, get_app_state, set_app_state
from src.api.routes import shortener


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = get_app_state()
    app.state.app_state = state
    try:
        yield
    finally:
        await state.dispose()
        set_app_state(None)


def create_app(state: AppState | None = None) -> FastAPI:
    if state is not None:
        set_app_state(state)
    app = FastAPI(title="Shorty", version="0.1.0", lifespan=lifespan)
    app.include_router(shortener.router)

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
