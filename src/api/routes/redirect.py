from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from src.api.dependencies import ResolveURLDep
from src.core.usecases.resolve_url import ResolveStatus

router = APIRouter()

_BASE62_RE = re.compile(r"^[0-9A-Za-z]+$")


@router.get("/{short_code}")
async def redirect_short_url(
    short_code: str,
    use_case: ResolveURLDep,
) -> RedirectResponse:
    if not _BASE62_RE.match(short_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="short code contains invalid characters (expected Base62: 0-9, A-Z, a-z)",
        )

    try:
        result = await use_case.execute(short_code)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid short code",
        ) from err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal server error",
        ) from err

    if result.status == ResolveStatus.OK:
        assert result.url is not None
        return RedirectResponse(url=result.url, status_code=status.HTTP_302_FOUND)
    if result.status == ResolveStatus.NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="short code not found",
        )
    if result.status == ResolveStatus.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this URL has been blocked",
        )
    if result.status == ResolveStatus.EXPIRED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This short link has expired",
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="unexpected resolver status",
    )
