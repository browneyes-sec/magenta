"""State management for missions and agents."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class InMemoryStateStore:
    """Simple in-memory state store (for dev/testing; Redis for prod)."""

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._ttl: dict[str, datetime] = {}

    async def set(self, key: str, value: Any, ttl_seconds: int = 0) -> None:
        self._data[key] = value
        if ttl_seconds > 0:
            self._ttl[key] = datetime.utcnow() + timedelta(seconds=ttl_seconds)

    async def get(self, key: str) -> Any | None:
        if key in self._ttl:
            if datetime.utcnow() > self._ttl[key]:
                await self.delete(key)
                return None
        return self._data.get(key)

    async def delete(self, key: str) -> bool:
        self._ttl.pop(key, None)
        return self._data.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        val = await self.get(key)
        return val is not None

    async def keys(self, pattern: str = "") -> list[str]:
        if pattern:
            return [k for k in self._data if pattern in k]
        return list(self._data.keys())

    async def clear(self) -> None:
        self._data.clear()
        self._ttl.clear()


class RedisStateStore:
    """Redis-backed state store with atomic SETNX for idempotency."""

    def __init__(self, redis_client):
        self._redis = redis_client

    async def set(self, key: str, value: Any, ttl_seconds: int = 0) -> None:
        dumped = json.dumps(value, default=str)
        if ttl_seconds > 0:
            await self._redis.setex(key, ttl_seconds, dumped)
        else:
            await self._redis.set(key, dumped)

    async def setnx(self, key: str, value: Any, ttl_seconds: int = 0) -> bool:
        """Atomically set if key does not exist. Returns True if set."""
        dumped = json.dumps(value, default=str)
        result = await self._redis.setnx(key, dumped)
        if result and ttl_seconds > 0:
            await self._redis.expire(key, ttl_seconds)
        return bool(result)

    async def get(self, key: str) -> Any | None:
        data = await self._redis.get(key)
        if data is None:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data

    async def delete(self, key: str) -> bool:
        deleted = await self._redis.delete(key)
        return deleted > 0

    async def exists(self, key: str) -> bool:
        return await self._redis.exists(key) > 0

    async def keys(self, pattern: str = "") -> list[str]:
        if pattern:
            return await self._redis.keys(pattern)
        return await self._redis.keys("*")

    async def clear(self) -> None:
        await self._redis.flushdb()


async def create_state_store(redis_url: str = "") -> Any:
    """Factory — returns RedisStateStore if Redis available, else InMemoryStateStore."""
    redis_url = redis_url or "redis://localhost:6379/0"
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(redis_url, decode_responses=True)
        await client.ping()
        store = RedisStateStore(client)
        logger.info("Using RedisStateStore at %s", redis_url)
        return store
    except Exception as exc:
        logger.warning("Redis unavailable (%s), falling back to InMemoryStateStore", exc)
        return InMemoryStateStore()


state_store = InMemoryStateStore()
