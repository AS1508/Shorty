from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from src.core.base62 import decode
from src.core.expiration import is_expired
from src.core.ports import CachePort, UrlRepository

_MAX_SNOWFLAKE = (1 << 63) - 1


class ResolveStatus(Enum):
    OK = "ok"
    NOT_FOUND = "not_found"
    BLOCKED = "blocked"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class ResolveResult:
    status: ResolveStatus
    url: str | None = None


class ResolveURL:
    _NOT_FOUND_SENTINEL = '{"s":"null"}'
    _BLOCKED_SENTINEL = '{"s":"blocked"}'
    _EXPIRED_SENTINEL = '{"s":"expired"}'

    def __init__(
        self,
        repository: UrlRepository,
        cache: CachePort,
    ) -> None:
        self._repository = repository
        self._cache = cache

    async def execute(self, code: str) -> ResolveResult:
        snowflake_id = decode(code)
        if snowflake_id > _MAX_SNOWFLAKE:
            return ResolveResult(status=ResolveStatus.NOT_FOUND)
        return await self._resolve(snowflake_id)

    async def _resolve(self, snowflake_id: int) -> ResolveResult:
        cache_key = str(snowflake_id)

        cached = await self._cache_get(cache_key)
        if cached is not None:
            return self._parse_cached(cached)

        record = await self._repository.find_by_id(snowflake_id)
        if record is None:
            await self._cache_set(cache_key, self._NOT_FOUND_SENTINEL, ttl=30)
            return ResolveResult(status=ResolveStatus.NOT_FOUND)

        if is_expired(record.expires_at):
            await self._cache_set(cache_key, self._EXPIRED_SENTINEL, ttl=300)
            return ResolveResult(status=ResolveStatus.EXPIRED)

        if record.is_blocked:
            await self._cache_set(cache_key, self._BLOCKED_SENTINEL, ttl=300)
            return ResolveResult(status=ResolveStatus.BLOCKED)

        expires = record.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        remaining_ttl = int((expires - datetime.now(UTC)).total_seconds())
        cache_ttl = max(remaining_ttl, 1)
        value = f'{{"s":"ok","u":"{record.original_url}"}}'
        await self._cache_set(cache_key, value, ttl=cache_ttl)
        return ResolveResult(status=ResolveStatus.OK, url=record.original_url)

    async def _cache_get(self, key: str) -> str | None:
        try:
            return await self._cache.get(key)
        except Exception:
            return None

    async def _cache_set(self, key: str, value: str, ttl: int) -> None:
        with contextlib.suppress(Exception):
            await self._cache.set(key, value, ttl)

    @staticmethod
    def _parse_cached(value: str) -> ResolveResult:
        try:
            data = json.loads(value)
            status = data["s"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return ResolveResult(status=ResolveStatus.NOT_FOUND)

        if status == "ok":
            return ResolveResult(status=ResolveStatus.OK, url=data.get("u") or "")
        if status == "blocked":
            return ResolveResult(status=ResolveStatus.BLOCKED)
        if status == "expired":
            return ResolveResult(status=ResolveStatus.EXPIRED)
        return ResolveResult(status=ResolveStatus.NOT_FOUND)
