from __future__ import annotations

import contextlib

from src.core import base62
from src.core.ports import CachePort, UrlRepository


class UnblockUrl:
    def __init__(self, repository: UrlRepository, cache: CachePort) -> None:
        self._repository = repository
        self._cache = cache

    async def execute(self, short_code: str) -> bool:
        snowflake_id = base62.decode(short_code)
        affected = await self._repository.update_blocked(snowflake_id, False)
        if affected == 0:
            return False

        with contextlib.suppress(Exception):
            await self._cache.delete(str(snowflake_id))

        return True
