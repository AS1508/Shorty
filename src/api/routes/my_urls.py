from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Response, status

from src.api.dependencies import AuthenticatedUserDep, MyUrlsRateLimitDep, SoftDeleteMyUrlDep

router = APIRouter(prefix="/my-urls")

_BASE62_RE = re.compile(r"^[0-9A-Za-z]+$")


@router.delete("/{short_code}")
async def delete_my_url(
    short_code: str,
    current_user: AuthenticatedUserDep,
    use_case: SoftDeleteMyUrlDep,
    _rate: MyUrlsRateLimitDep,
) -> Response:
    if not _BASE62_RE.match(short_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="short code contains invalid characters (expected Base62: 0-9, A-Z, a-z)",
        )

    deleted = await use_case.execute(short_code, current_user)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="short code not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
