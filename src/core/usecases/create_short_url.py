from __future__ import annotations

from datetime import UTC, datetime

from src.core import base62
from src.core.expiration import URL_TTL_SECONDS, calculate_expires_at, is_expired
from src.core.ports import CachePort, IdGenerator, UrlRecord, UrlRepository


class CreateShortURL:
    def __init__(
        self,
        id_generator: IdGenerator,
        repository: UrlRepository,
        base_url: str,
        cache: CachePort,
    ) -> None:
        self._id_generator = id_generator
        self._repository = repository
        self._base_url = base_url.rstrip("/")
        self._cache = cache

    async def execute(self, original_url: str, *, created_by: str | None = None) -> str:
        snowflake_id = self._id_generator.next_id()
        created_at = datetime.now(UTC)
        record = UrlRecord(
            id=snowflake_id,
            original_url=original_url,
            created_at=created_at,
            expires_at=calculate_expires_at(created_at),
            created_by=created_by,
        )
        existing = await self._repository.find_by_id(snowflake_id)
        if existing is not None and is_expired(existing.expires_at):
            await self._repository.delete_expired()
        await self._repository.insert(record)
        code = base62.encode(snowflake_id)
        import contextlib
        with contextlib.suppress(Exception):
            cache_value = f'{{"s":"ok","u":"{original_url}"}}'
            await self._cache.set(str(snowflake_id), cache_value, URL_TTL_SECONDS)
        return f"{self._base_url}/{code}"
