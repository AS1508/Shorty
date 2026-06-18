from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from src.api.dependencies import (
    AdminUserDep,
    BlockUrlDep,
    ListAllUrlsDep,
    RepositoryDep,
    SettingsDep,
    UnblockUrlDep,
)
from src.core import base62
from src.core.expiration import is_expired
from src.core.usecases.list_all_urls import ListAllUrlsItem

router = APIRouter(prefix="/admin")

_BASE62_RE = re.compile(r"^[0-9A-Za-z]+$")
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


def _build_item(item: ListAllUrlsItem, base_url: str) -> dict[str, Any]:
    code = base62.encode(item.id)
    return {
        "short_code": code,
        "short_url": f"{base_url}/{code}",
        "original_url": item.original_url,
        "created_at": item.created_at.isoformat(),
        "expires_at": item.expires_at.isoformat(),
        "is_expired": item.is_expired,
        "is_blocked": item.is_blocked,
        "created_by": item.created_by,
        "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
        "clicks": item.clicks,
    }


@router.post("/block/{short_code}")
async def block_url(
    short_code: str,
    current_user: AdminUserDep,
    use_case: BlockUrlDep,
) -> dict[str, str]:
    if not _BASE62_RE.match(short_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="short code contains invalid characters",
        )

    ok = await use_case.execute(short_code)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="short code not found")
    return {"status": "blocked"}


@router.post("/unblock/{short_code}")
async def unblock_url(
    short_code: str,
    current_user: AdminUserDep,
    use_case: UnblockUrlDep,
) -> dict[str, str]:
    if not _BASE62_RE.match(short_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="short code contains invalid characters",
        )

    ok = await use_case.execute(short_code)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="short code not found")
    return {"status": "unblocked"}


@router.get("/urls")
async def list_all_urls(
    current_user: AdminUserDep,
    use_case: ListAllUrlsDep,
    settings: SettingsDep,
    cursor: int | None = Query(default=None, ge=1),
    limit: int = Query(default=_DEFAULT_LIMIT),
) -> dict[str, Any]:
    limit = max(1, min(limit, _MAX_LIMIT))
    result = await use_case.execute(cursor, limit)
    urls = [_build_item(item, settings.short_base_url) for item in result.items]
    response: dict[str, Any] = {"urls": urls, "has_more": result.has_more}
    if result.has_more and result.items:
        response["next_cursor"] = str(result.items[-1].id)
    return response


@router.get("/stats/{short_code}")
async def admin_stats(
    short_code: str,
    current_user: AdminUserDep,
    repository: RepositoryDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    if not _BASE62_RE.match(short_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="short code contains invalid characters",
        )

    snowflake_id = base62.decode(short_code)
    record = await repository.find_by_id(snowflake_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="short code not found")

    code = base62.encode(record.id)
    return {
        "short_code": code,
        "short_url": f"{settings.short_base_url}/{code}",
        "original_url": record.original_url,
        "created_at": record.created_at.isoformat(),
        "expires_at": record.expires_at.isoformat(),
        "is_expired": is_expired(record.expires_at),
        "is_blocked": record.is_blocked,
        "created_by": record.created_by,
        "deleted_at": record.deleted_at.isoformat() if record.deleted_at else None,
        "clicks": record.clicks,
    }
