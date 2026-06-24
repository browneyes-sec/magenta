"""Tests for shared RedisManager: connection pooling, fallback, health checks."""

from __future__ import annotations

import asyncio
import os

import pytest


class TestRedisManagerInMemoryFallback:
    """When MAGENTA_REDIS_PERSISTENCE=false (default), RedisManager uses in-memory."""

    def test_singleton_exists(self):
        from magenta.core.redis_manager import redis_manager
        assert redis_manager is not None
        assert redis_manager.persistence_mode == "memory"

    @pytest.mark.asyncio
    async def test_initialize_without_redis(self):
        from magenta.core.redis_manager import RedisManager
        mgr = RedisManager()
        mgr._persistence_enabled = False
        await mgr.initialize()
        assert mgr.persistence_mode == "memory"
        assert mgr.is_available is False

    @pytest.mark.asyncio
    async def test_save_json_noop_when_disabled(self):
        from magenta.core.redis_manager import RedisManager
        mgr = RedisManager()
        mgr._persistence_enabled = False
        await mgr.initialize()
        result = await mgr.save_json("test:key", {"a": 1})
        assert result is False

    @pytest.mark.asyncio
    async def test_load_json_returns_none_when_disabled(self):
        from magenta.core.redis_manager import RedisManager
        mgr = RedisManager()
        mgr._persistence_enabled = False
        await mgr.initialize()
        data = await mgr.load_json("test:key")
        assert data is None

    @pytest.mark.asyncio
    async def test_remove_returns_false_when_disabled(self):
        from magenta.core.redis_manager import RedisManager
        mgr = RedisManager()
        mgr._persistence_enabled = False
        await mgr.initialize()
        result = await mgr.remove("test:key")
        assert result is False

    @pytest.mark.asyncio
    async def test_keys_returns_empty_when_disabled(self):
        from magenta.core.redis_manager import RedisManager
        mgr = RedisManager()
        mgr._persistence_enabled = False
        await mgr.initialize()
        keys = await mgr.keys("test:*")
        assert keys == []

    @pytest.mark.asyncio
    async def test_health_when_disabled(self):
        from magenta.core.redis_manager import RedisManager
        mgr = RedisManager()
        mgr._persistence_enabled = False
        await mgr.initialize()
        health = await mgr.health()
        assert health["status"] == "disabled"
        assert health["mode"] == "memory"

    @pytest.mark.asyncio
    async def test_get_or_set_calls_factory_when_disabled(self):
        from magenta.core.redis_manager import RedisManager
        mgr = RedisManager()
        mgr._persistence_enabled = False
        await mgr.initialize()

        factory_called = False

        def factory():
            nonlocal factory_called
            factory_called = True
            return {"computed": True}

        result = await mgr.get_or_set("test:key", factory)
        assert factory_called is True
        assert result == {"computed": True}

    @pytest.mark.asyncio
    async def test_close_without_client(self):
        from magenta.core.redis_manager import RedisManager
        mgr = RedisManager()
        mgr._persistence_enabled = False
        await mgr.initialize()
        await mgr.close()  # Should not raise


class TestRedisManagerMetrics:
    """Test metrics attributes on RedisManager."""

    def test_initial_metrics_values(self):
        from magenta.core.redis_manager import RedisManager
        mgr = RedisManager()
        assert mgr.persistence_mode == "memory"
        assert mgr.redis_connections_active == 0
        assert mgr.redis_latency_ms == 0.0
        assert mgr.cache_hits == 0
        assert mgr.cache_misses == 0

    @pytest.mark.asyncio
    async def test_health_degraded_when_ping_fails(self):
        from magenta.core.redis_manager import RedisManager
        mgr = RedisManager()
        mgr._persistence_enabled = True
        mgr._redis_url = "redis://nonexistent:99999"
        await mgr.initialize()
        health = await mgr.health()
        assert health["status"] == "degraded"
        assert health["mode"] == "memory"
