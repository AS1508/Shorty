from __future__ import annotations

import logging
import time
import urllib.parse
from dataclasses import dataclass

from src.core.ports import CachePort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int


class FixedWindowRateLimiter:
    def __init__(self, cache: CachePort, key_prefix: str, limit: int, window_seconds: int) -> None:
        self._cache = cache
        self._key_prefix = key_prefix
        self._limit = limit
        self._window_seconds = window_seconds

    async def check(self, client_key: str) -> RateLimitResult:
        now_seconds = int(time.time())
        window_ts = (now_seconds // self._window_seconds) * self._window_seconds
        safe_key = _sanitize_key(client_key)
        redis_key = f"{self._key_prefix}:{safe_key}:{window_ts}"

        count = await self._cache.incr(redis_key)
        if count is None:
            return RateLimitResult(allowed=True, retry_after_seconds=0)

        await self._cache.expire(redis_key, self._window_seconds)

        if count > self._limit:
            retry_after = self._window_seconds - (now_seconds % self._window_seconds)
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

        return RateLimitResult(allowed=True, retry_after_seconds=0)

    @staticmethod
    def extract_client_ip(forwarded: str | None, client_host: str | None) -> str:
        if forwarded:
            return forwarded.split(",")[-1].strip()
        if client_host:
            return client_host
        return "unknown"


def _sanitize_key(raw: str) -> str:
    return urllib.parse.quote(raw, safe="")
