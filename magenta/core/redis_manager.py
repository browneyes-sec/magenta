"""Shared Redis connection manager with connection pooling and in-memory fallback.

Provides a singleton RedisManager for all persistence consumers
(MissionManager, WorkflowEngine, DurableApprovalStore, dictator_state).

Feature flag: MAGENTA_REDIS_PERSISTENCE=true enables Redis persistence.
When false or Redis is unavailable, falls back to in-memory dict.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


class RedisManager:
    """Shared Redis connection manager with pooling, health checks, and fallback.

    Usage:
        from magenta.core.redis_manager import redis_manager
        await redis_manager.initialize()
        await redis_manager.save_json("mission:abc", {"status": "running"}, ttl=3600)
        data = await redis_manager.load_json("mission:abc")
    """

    def __init__(self):
        self._redis_url = os.getenv(
            "MAGENTA_REDIS_URL",
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        )
        self._persistence_enabled = (
            os.getenv("MAGENTA_REDIS_PERSISTENCE", "false").lower() == "true"
        )
        self._client = None
        self._initialized = False
        self._degraded = False

        # Metrics
        self.persistence_mode: str = "memory"  # "redis" | "memory"
        self.redis_connections_active: int = 0
        self.redis_latency_ms: float = 0.0
        self.cache_hits: int = 0
        self.cache_misses: int = 0

    async def initialize(self) -> None:
        """Connect to Redis if persistence is enabled. Falls back to in-memory."""
        if self._initialized:
            return
        if not self._persistence_enabled:
            logger.info("Redis persistence disabled, using in-memory storage")
            self.persistence_mode = "memory"
            self._initialized = True
            return

        try:
            import redis.asyncio as aioredis

            pool = aioredis.ConnectionPool.from_url(
                self._redis_url,
                decode_responses=True,
                max_connections=10,
                retry_on_timeout=True,
            )
            client = aioredis.Redis(connection_pool=pool)

            start = time.monotonic()
            await client.ping()
            latency = (time.monotonic() - start) * 1000

            self._client = client
            self._initialized = True
            self._degraded = False
            self.persistence_mode = "redis"
            self.redis_connections_active = pool.connection_kwargs.get("max_connections", 10)
            self.redis_latency_ms = round(latency, 2)
            logger.info(
                "Redis connected at %s (latency: %.1fms)",
                self._redis_url,
                latency,
            )
        except Exception as exc:
            logger.warning(
                "Redis unavailable at %s, falling back to in-memory: %s",
                self._redis_url,
                exc,
            )
            self._degraded = True
            self.persistence_mode = "memory"
            self._initialized = True

    async def health(self) -> dict[str, Any]:
        """Check Redis health. Returns status dict."""
        if not self._client:
            return {
                "status": "degraded" if self._degraded else "disabled",
                "mode": self.persistence_mode,
            }

        try:
            start = time.monotonic()
            await self._client.ping()
            latency = (time.monotonic() - start) * 1000
            self.redis_latency_ms = round(latency, 2)
            return {
                "status": "ok",
                "mode": "redis",
                "latency_ms": self.redis_latency_ms,
            }
        except Exception as exc:
            return {
                "status": "degraded",
                "mode": "memory",
                "error": str(exc),
            }

    async def save_json(self, key: str, data: dict | list, ttl: int | None = None) -> bool:
        """Serialize and save JSON data to Redis. Returns True on success."""
        if not self._client:
            return False
        try:
            value = json.dumps(data, default=str)
            if ttl:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
            return True
        except Exception as exc:
            logger.debug("Redis save_json failed for %s: %s", key, exc)
            return False

    async def load_json(self, key: str) -> dict | list | None:
        """Load and deserialize JSON data from Redis. Returns None if not found."""
        if not self._client:
            return None
        try:
            value = await self._client.get(key)
            if value is None:
                self.cache_misses += 1
                return None
            self.cache_hits += 1
            return json.loads(value)
        except Exception as exc:
            logger.debug("Redis load_json failed for %s: %s", key, exc)
            return None

    async def remove(self, key: str) -> bool:
        """Delete a key from Redis. Returns True on success."""
        if not self._client:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception:
            return False

    async def keys(self, pattern: str) -> list[str]:
        """List keys matching a pattern. Returns empty list if unavailable."""
        if not self._client:
            return []
        try:
            return await self._client.keys(pattern)
        except Exception:
            return []

    async def get_or_set(
        self, key: str, factory: Any, ttl: int | None = None
    ) -> dict | list | None:
        """Cache-through: load from Redis, or call factory() and save result."""
        data = await self.load_json(key)
        if data is not None:
            return data

        if callable(factory):
            data = await factory() if callable(getattr(factory, "__await__", None)) else factory()
        else:
            data = factory

        if data is not None:
            await self.save_json(key, data, ttl=ttl)
        return data

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self._client:
            try:
                await self._client.close()
                logger.info("Redis connection pool closed")
            except Exception:
                pass
            self._client = None
            self.redis_connections_active = 0

    @property
    def is_available(self) -> bool:
        """True if Redis client is connected and not degraded."""
        return self._client is not None and not self._degraded


# Module-level singleton
redis_manager = RedisManager()
