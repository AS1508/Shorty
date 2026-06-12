from __future__ import annotations

import contextlib
import logging

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, redis_url: str) -> None:
        self._client = aioredis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        try:
            return await self._client.get(key)  # type: ignore[return-value]
        except aioredis.ConnectionError:
            logger.warning("redis unavailable for GET %s, falling through", key)
            return None
        except Exception:
            logger.warning("redis GET %s failed, falling through", key, exc_info=True)
            return None

    async def set(self, key: str, value: str, ttl: int) -> None:
        try:
            await self._client.set(key, value, ex=ttl)
        except aioredis.ConnectionError:
            logger.warning("redis unavailable for SET %s, skipped", key)
        except Exception:
            logger.warning("redis SET %s failed, skipped", key, exc_info=True)

    async def incr(self, key: str) -> int | None:
        try:
            return await self._client.incr(key)
        except aioredis.ConnectionError:
            logger.warning("redis unavailable for INCR %s, falling through", key)
            return None
        except Exception:
            logger.warning("redis INCR %s failed, falling through", key, exc_info=True)
            return None

    async def expire(self, key: str, ttl: int) -> None:
        try:
            await self._client.expire(key, ttl)
        except aioredis.ConnectionError:
            logger.warning("redis unavailable for EXPIRE %s, skipped", key)
        except Exception:
            logger.warning("redis EXPIRE %s failed, skipped", key, exc_info=True)

    async def aclose(self) -> None:
        with contextlib.suppress(Exception):
            await self._client.aclose()

    async def close(self) -> None:  # deprecated alias, kept for compat
        await self.aclose()
