"""Tests for Dictator API — FastAPI TestClient validation of all 14 endpoints."""

import pytest
from fastapi.testclient import TestClient

from magenta.api.server import create_app


@pytest.fixture
def client():
    """FastAPI TestClient with fresh app instance."""
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestDictatorAPIStatus:
    def test_get_framework_status(self, client):
        resp = client.get("/api/v1/dictator/framework")
        assert resp.status_code == 200
        data = resp.json()
        assert "dictator" in data
        assert "registry" in data
        assert "missions" in data

    def test_get_dictator_status(self, client):
        resp = client.get("/api/v1/dictator/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "dictator" in data

    def test_get_oversight_board(self, client):
        resp = client.get("/api/v1/dictator/oversight")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_missions" in data

    def test_get_oversight_mission_not_found(self, client):
        resp = client.get("/api/v1/dictator/oversight/nonexistent")
        assert resp.status_code == 404

    def test_get_directives(self, client):
        resp = client.get("/api/v1/dictator/directives")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestDictatorAPIDirectives:
    def test_issue_directive(self, client):
        resp = client.post(
            "/api/v1/dictator/directives",
            params={
                "directive_type": "deploy_agent",
                "target": "triage",
                "reason": "API test",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "issued"
        assert "directive_id" in data

    def test_issue_invalid_directive_type(self, client):
        resp = client.post(
            "/api/v1/dictator/directives",
            params={
                "directive_type": "invalid_type",
                "target": "test",
            },
        )
        assert resp.status_code == 400

    def test_issue_directive_with_payload(self, client):
        resp = client.post(
            "/api/v1/dictator/directives",
            params={
                "directive_type": "inject_probe",
                "target": "enrich",
                "mission_id": "m-99",
                "reason": "Need probes",
            },
            json={"probe_points": ["pre", "post"]},
        )
        assert resp.status_code == 200

    def test_halt_mission(self, client):
        resp = client.post("/api/v1/dictator/halt/test-mission", params={"reason": "API halt"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "halted"

    def test_escalate_mission(self, client):
        resp = client.post("/api/v1/dictator/escalate/test-mission")
        assert resp.status_code == 200
        assert resp.json()["status"] == "escalated"


class TestDictatorAPIAgents:
    def test_deploy_agent(self, client):
        resp = client.post("/api/v1/dictator/deploy/triage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deployed"
        assert data["role"] == "triage"

    def test_deploy_agent_with_model(self, client):
        resp = client.post("/api/v1/dictator/deploy/enrich", params={"model": "mistral:7b"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "enrich"

    def test_recall_agent_not_found(self, client):
        resp = client.delete("/api/v1/dictator/agents/nonexistent")
        assert resp.status_code == 404

    def test_recall_agent_success(self, client):
        deploy = client.post("/api/v1/dictator/deploy/triage")
        agent_id = deploy.json()["agent_id"]
        resp = client.delete(f"/api/v1/dictator/agents/{agent_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "recalled"


class TestDictatorAPITeaming:
    def test_override_teaming(self, client):
        resp = client.post(
            "/api/v1/dictator/teaming/test-mission",
            params={"structure": "debate"},
        )
        assert resp.status_code == 200
        assert resp.json()["teaming"] == "debate"

    def test_override_invalid_teaming(self, client):
        resp = client.post(
            "/api/v1/dictator/teaming/test-mission",
            params={"structure": "invalid_structure"},
        )
        assert resp.status_code == 400

    def test_override_teaming_pipeline(self, client):
        resp = client.post(
            "/api/v1/dictator/teaming/test-mission",
            params={"structure": "pipeline"},
        )
        assert resp.status_code == 200


class TestDictatorAPIPolicies:
    def test_list_policies(self, client):
        resp = client.get("/api/v1/dictator/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert "policies" in data
        assert len(data["policies"]) == 4

    def test_apply_policy_override(self, client):
        resp = client.post(
            "/api/v1/dictator/policies/override",
            json={"name": "test_override", "rules": {"teaming": "mesh"}},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "override_applied"

    def test_clear_policy_overrides(self, client):
        resp = client.delete("/api/v1/dictator/policies/overrides")
        assert resp.status_code == 200
        assert resp.json()["status"] == "overrides_cleared"


class TestDictatorAPIProbes:
    def test_promote_probe(self, client):
        resp = client.post(
            "/api/v1/dictator/probes/promote",
            params={"name": "memory_scan", "guard": True},
        )
        assert resp.status_code == 200
        assert resp.json()["probe"] == "memory_scan"

    def test_promote_probe_no_guard(self, client):
        resp = client.post(
            "/api/v1/dictator/probes/promote",
            params={"name": "network_tap"},
        )
        assert resp.status_code == 200
