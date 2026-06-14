from __future__ import annotations

import contextlib

from src.core import base62
from src.core.ports import CachePort, UrlRepository


class SoftDeleteMyUrl:
    def __init__(self, repository: UrlRepository, cache: CachePort) -> None:
        self._repository = repository
        self._cache = cache

    async def execute(self, short_code: str, current_user: str) -> bool:
        snowflake_id = base62.decode(short_code)

        record = await self._repository.find_by_id(snowflake_id)
        if record is None:
            return False

        if record.created_by != current_user:
            return False

        if record.deleted_at is not None:
            return False

        affected = await self._repository.soft_delete(snowflake_id)
        if affected == 0:
            return False

        with contextlib.suppress(Exception):
            await self._cache.delete(str(snowflake_id))

        return True
