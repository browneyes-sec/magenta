"""Integration tests for API middleware.

Tests rate limiting, correlation ID propagation, and auth guard behavior.
Uses a lightweight FastAPI app to avoid the full server lifespan chain.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from magenta.api.middleware import (
    CorrelationIDMiddleware,
    RateLimiter,
    RateLimitMiddleware,
)


@pytest.fixture()
def app_with_middleware():
    """Create a minimal FastAPI app with rate limit + correlation middlewares."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, max_requests=3, window_seconds=60)
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/api/v1/workflows")
    async def workflows_endpoint():
        return {"workflows": []}

    return app


@pytest.fixture()
def app_with_high_limit():
    """App with higher rate limit for correlation ID tests."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, max_requests=1000, window_seconds=60)
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    return app


class TestRateLimiter:
    """Unit tests for the RateLimiter sliding window."""

    def test_allows_requests_under_limit(self):
        limiter = RateLimiter()

        async def _check():
            for _ in range(5):
                ok = await limiter.check("key1", max_requests=10, window_seconds=60)
                assert ok

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_check())
        finally:
            loop.close()

    def test_blocks_requests_over_limit(self):
        limiter = RateLimiter()

        async def _check():
            for _ in range(5):
                await limiter.check("key2", max_requests=5, window_seconds=60)
            return await limiter.check("key2", max_requests=5, window_seconds=60)

        loop = asyncio.new_event_loop()
        try:
            assert not loop.run_until_complete(_check())
        finally:
            loop.close()

    def test_different_keys_independent(self):
        limiter = RateLimiter()

        async def _check():
            for _ in range(5):
                await limiter.check("a", max_requests=5, window_seconds=60)
            blocked = not await limiter.check("a", max_requests=5, window_seconds=60)
            allowed = await limiter.check("b", max_requests=5, window_seconds=60)
            return blocked, allowed

        loop = asyncio.new_event_loop()
        try:
            blocked, allowed = loop.run_until_complete(_check())
            assert blocked
            assert allowed
        finally:
            loop.close()


class TestRateLimitMiddleware:
    """Integration tests for the rate limiting middleware."""

    def test_allows_requests_under_limit(self, app_with_middleware):
        with TestClient(app_with_middleware, raise_server_exceptions=False) as client:
            for _ in range(3):
                resp = client.get("/test")
                assert resp.status_code == 200

    def test_returns_429_when_exceeded(self, app_with_middleware):
        with TestClient(app_with_middleware, raise_server_exceptions=False) as client:
            for _ in range(3):
                client.get("/test")
            resp = client.get("/test")
            assert resp.status_code == 429
            assert "Rate limit exceeded" in resp.json()["detail"]

    def test_excluded_paths_bypass_rate_limit(self, app_with_middleware):
        with TestClient(app_with_middleware, raise_server_exceptions=False) as client:
            for _ in range(10):
                resp = client.get("/")
                # Root returns 404 (no route) but should NOT return 429
                assert resp.status_code != 429

    def test_metrics_path_bypasses_rate_limit(self, app_with_middleware):
        with TestClient(app_with_middleware, raise_server_exceptions=False) as client:
            for _ in range(10):
                resp = client.get("/metrics")
                assert resp.status_code in (200, 404)


class TestCorrelationIDMiddleware:
    """Integration tests for correlation ID propagation."""

    def test_generates_correlation_id_when_not_provided(self, app_with_high_limit):
        with TestClient(app_with_high_limit, raise_server_exceptions=False) as client:
            resp = client.get("/test")
            assert "X-Correlation-ID" in resp.headers
            assert resp.headers["X-Correlation-ID"].startswith("req-")

    def test_preserves_provided_correlation_id(self, app_with_high_limit):
        with TestClient(app_with_high_limit, raise_server_exceptions=False) as client:
            cid = "req-customid123"
            resp = client.get("/test", headers={"X-Correlation-ID": cid})
            assert resp.headers["X-Correlation-ID"] == cid

    def test_different_requests_get_different_ids(self, app_with_high_limit):
        with TestClient(app_with_high_limit, raise_server_exceptions=False) as client:
            resp1 = client.get("/test")
            resp2 = client.get("/test")
            assert resp1.headers["X-Correlation-ID"] != resp2.headers["X-Correlation-ID"]
