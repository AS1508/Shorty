from __future__ import annotations

from datetime import UTC, datetime

from src.core import base62
from src.core.ports import IdGenerator, UrlRecord, UrlRepository


class CreateShortURL:
    def __init__(
        self,
        id_generator: IdGenerator,
        repository: UrlRepository,
        base_url: str,
    ) -> None:
        self._id_generator = id_generator
        self._repository = repository
        self._base_url = base_url.rstrip("/")

    async def execute(self, original_url: str) -> str:
        snowflake_id = self._id_generator.next_id()
        code = base62.encode(snowflake_id)
        record = UrlRecord(
            id=snowflake_id,
            original_url=original_url,
            created_at=datetime.now(UTC),
        )
        await self._repository.insert(record)
        return f"{self._base_url}/{code}"
