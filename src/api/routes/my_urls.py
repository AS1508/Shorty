from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status

from src.api.dependencies import (
    AuthenticatedUserDep,
    GetMyUrlDep,
    ListMyUrlsDep,
    MyUrlsRateLimitDep,
    SettingsDep,
    SoftDeleteMyUrlDep,
)
from src.core import base62
from src.core.expiration import is_expired
from src.core.usecases.list_my_urls import ListMyUrlsItem

router = APIRouter(prefix="/my-urls")

_BASE62_RE = re.compile(r"^[0-9A-Za-z]+$")
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


def _build_item(item: ListMyUrlsItem, base_url: str) -> dict[str, Any]:
    code = base62.encode(item.id)
    return {
        "short_code": code,
        "short_url": f"{base_url}/{code}",
        "original_url": item.original_url,
        "created_at": item.created_at.isoformat(),
        "expires_at": item.expires_at.isoformat(),
        "is_expired": item.is_expired,
        "is_blocked": item.is_blocked,
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
    }


@router.get("")
async def list_my_urls(
    current_user: AuthenticatedUserDep,
    use_case: ListMyUrlsDep,
    settings: SettingsDep,
    _rate: MyUrlsRateLimitDep,
    cursor: int | None = Query(default=None, ge=1),
    limit: int = Query(default=_DEFAULT_LIMIT),
) -> dict[str, Any]:
    limit = max(1, min(limit, _MAX_LIMIT))
    result = await use_case.execute(current_user, cursor, limit)
    urls = [_build_item(item, settings.short_base_url) for item in result.items]
    response: dict[str, Any] = {"urls": urls, "has_more": result.has_more}
    if result.has_more and result.items:
        response["next_cursor"] = str(result.items[-1].id)
    return response


@router.get("/{short_code}")
async def get_my_url(
    short_code: str,
    current_user: AuthenticatedUserDep,
    use_case: GetMyUrlDep,
    settings: SettingsDep,
    _rate: MyUrlsRateLimitDep,
) -> dict[str, Any]:
    if not _BASE62_RE.match(short_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="short code contains invalid characters (expected Base62: 0-9, A-Z, a-z)",
        )

    record = await use_case.execute(short_code, current_user)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="short code not found"
        )

    code = base62.encode(record.id)
    return {
        "short_code": code,
        "short_url": f"{settings.short_base_url}/{code}",
        "original_url": record.original_url,
        "created_at": record.created_at.isoformat(),
        "expires_at": record.expires_at.isoformat(),
        "is_expired": is_expired(record.expires_at),
        "is_blocked": record.is_blocked,
        "deleted_at": record.deleted_at.isoformat() if record.deleted_at else None,
    }


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
