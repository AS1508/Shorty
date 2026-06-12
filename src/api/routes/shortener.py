from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from src.api.dependencies import AuthenticatedUserDep, CreateShortURLDep, RateLimitCreateDep
from src.api.schemas import URL_MAX_LENGTH, CreateURLRequest, CreateURLResponse
from src.core.snowflake import InvalidSystemClock

router = APIRouter()


@router.post(
    "/Create-URL",
    response_model=CreateURLResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_url(
    payload: CreateURLRequest,
    use_case: CreateShortURLDep,
    authenticated_user: AuthenticatedUserDep,
    rate_limit: RateLimitCreateDep,
) -> CreateURLResponse:
    url_str = payload.url_str
    if len(url_str) > URL_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"url length {len(url_str)} exceeds maximum of {URL_MAX_LENGTH} characters",
        )
    try:
        short_url = await use_case.execute(url_str, created_by=authenticated_user)
    except InvalidSystemClock as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="server clock is out of sync; cannot mint new ids",
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.errors()[0]["msg"],
        ) from exc
    except Exception as exc:  # noqa: BLE001 - fail closed on persistence or any other unexpected error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal server error",
        ) from exc
    return CreateURLResponse(short_url=short_url)
