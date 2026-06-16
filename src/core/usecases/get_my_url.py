from __future__ import annotations

from src.core import base62
from src.core.ports import UrlRecord, UrlRepository


class GetMyUrl:
    def __init__(self, repository: UrlRepository) -> None:
        self._repository = repository

    async def execute(self, short_code: str, current_user: str) -> UrlRecord | None:
        snowflake_id = base62.decode(short_code)
        record = await self._repository.find_by_id(snowflake_id)
        if record is None:
            return None
        if record.created_by != current_user:
            return None
        return record
