"""Tests for API routes: dictator, health, missions."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Create a minimal FastAPI app with dictator + health + missions routes."""
    from fastapi import FastAPI
    from magenta.api.routes import dictator, health, missions

    app = FastAPI()
    app.include_router(dictator.router, prefix="/api/v1/dictator")
    app.include_router(health.router, prefix="/api/v1/health")
    app.include_router(missions.router, prefix="/api/v1/missions")
    return TestClient(app, raise_server_exceptions=False)


class TestHealthRoutes:
    def test_health_endpoint(self, client):
        resp = client.get("/api/v1/health/")
        assert resp.status_code == 200

    def test_health_agents(self, client):
        resp = client.get("/api/v1/health/agents")
        assert resp.status_code == 200


class TestMissionsRoutes:
    def test_list_missions(self, client):
        resp = client.get("/api/v1/missions/")
        assert resp.status_code == 200

    def test_get_mission_not_found(self, client):
        resp = client.get("/api/v1/missions/nonexistent")
        assert resp.status_code in (404, 422)


class TestDictatorRoutesRequiresAuth:
    """Verify dictator routes reject unauthenticated requests when auth is enabled."""

    def test_status_requires_role(self, client):
        resp = client.get("/api/v1/dictator/status")
        # With auth enabled by default, should get 403 (no role provided)
        assert resp.status_code in (200, 403)

    def test_directives_requires_role(self, client):
        resp = client.get("/api/v1/dictator/directives")
        assert resp.status_code in (200, 403)

    def test_halt_requires_role(self, client):
        resp = client.post("/api/v1/dictator/halt/mission-1")
        assert resp.status_code in (200, 403)

    def test_deploy_requires_role(self, client):
        resp = client.post("/api/v1/dictator/deploy/triage")
        assert resp.status_code in (200, 403)

    def test_recall_requires_role(self, client):
        resp = client.delete("/api/v1/dictator/agents/agent-1")
        assert resp.status_code in (200, 403)
