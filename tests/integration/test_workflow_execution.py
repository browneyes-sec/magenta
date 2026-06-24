"""Integration tests for workflow engine execution.

Tests full DAG execution with mock agents, approval gates, and subgraphs.
Uses TestClient for API contract validation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from magenta.api.routes import workflows
from magenta.core.agent import BaseAgent, agent_registry
from magenta.core.mission import mission_manager
from magenta.core.models import AgentConfig, PlaybookV2
from magenta.workflows.compiler import workflow_compiler
from magenta.workflows.engine import WorkflowEngine, WorkflowExecution, workflow_engine

# Create a lightweight test app without the server lifespan
_test_app = None


def _get_test_app():
    global _test_app
    if _test_app is None:
        _test_app = FastAPI()
        _test_app.include_router(workflows.router, prefix="/api/v1/workflows")
    return _test_app


# ── Mock Agent for Testing ──────────────────────────────────────────────


class MockSOCAgent(BaseAgent):
    """Mock agent that returns predictable results for testing."""

    def __init__(self, config: AgentConfig | None = None):
        if config is None:
            config = AgentConfig(
                agent_id="mock-soc-agent",
                role="analyst",
                max_concurrent_tasks=5,
            )
        super().__init__(config)

    async def _process_impl(self, mission, context):
        return {
            "agent_id": self.config.agent_id,
            "status": "completed",
            "findings": [],
        }

    async def _execute_tool_impl(self, tool_name, params):
        return None


@pytest.fixture
def client():
    """Create test client with mock auth via X-Magenta-Role header."""
    with TestClient(_get_test_app()) as c:
        c.headers["Authorization"] = "Bearer mock-dev-token-1"
        c.headers["X-Magenta-Role"] = "operator"
        yield c


@pytest.fixture(autouse=True)
def setup_agents():
    """Register mock agents for all workflow roles."""
    agent_registry._agents.clear()
    roles = ["analyst", "ingest", "triage", "enrich", "contain", "compliance", "report"]
    for role in roles:
        agent = MockSOCAgent(
            AgentConfig(agent_id=f"mock-{role}-agent", role=role, max_concurrent_tasks=5)
        )
        agent_registry.register(agent)
    yield
    agent_registry._agents.clear()


@pytest.fixture(autouse=True)
def cleanup_executions():
    """Clean up workflow engine state between tests."""
    workflow_engine._executions.clear()
    workflow_engine._running_missions.clear()
    workflow_engine._approval_callbacks.clear()
    yield
    workflow_engine._executions.clear()
    workflow_engine._running_missions.clear()
    workflow_engine._approval_callbacks.clear()


# ── API Contract Tests ─────────────────────────────────────────────────


class TestAPIContracts:
    """Test API endpoints return correct schemas."""

    def test_list_playbooks(self, client):
        resp = client.get("/api/v1/workflows/playbooks")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_subgraphs(self, client):
        resp = client.get("/api/v1/workflows/subgraphs/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "subgraphs" in data

    def test_list_tools(self, client):
        resp = client.get("/api/v1/workflows/tools/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data


# ── Role-Based Access Control ──────────────────────────────────────────


class TestRoleBasedAccess:
    """Test RBAC enforcement on workflow endpoints."""

    def test_execute_requires_operator_or_admin(self, client):
        client.headers["X-Magenta-Role"] = "viewer"
        resp = client.post(
            "/api/v1/workflows/execute",
            json={"playbook_path": "test.yaml", "alert_id": "test-001"},
        )
        assert resp.status_code == 403

    def test_viewer_can_read(self, client):
        client.headers["X-Magenta-Role"] = "viewer"
        resp = client.get("/api/v1/workflows/playbooks")
        assert resp.status_code == 200

    def test_operator_can_execute(self, client):
        client.headers["X-Magenta-Role"] = "operator"
        resp = client.post(
            "/api/v1/workflows/execute",
            json={"playbook_path": "test.yaml", "alert_id": "test-001"},
        )
        # May return 404/500 for missing playbook, but not 403
        assert resp.status_code != 403

    def test_no_role_returns_403(self, client):
        client.headers.pop("X-Magenta-Role", None)
        resp = client.get("/api/v1/workflows/playbooks")
        assert resp.status_code == 403


# ── Workflow Execution (Fire-and-Forget) ───────────────────────────────


class TestWorkflowExecution:
    """Test workflow execution via API."""

    def test_execute_with_playbook_path(self, client):
        playbook_path = str(
            Path(__file__).parent.parent.parent
            / "magenta/workflows/examples/phishing-investigation.yaml"
        )
        resp = client.post(
            "/api/v1/workflows/execute",
            json={
                "playbook_path": playbook_path,
                "alert_id": "integration-test-001",
                "source_system": "sentinel",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert "mission_id" in data

    def test_execute_requires_alert_id(self, client):
        resp = client.post(
            "/api/v1/workflows/execute",
            json={"playbook_path": "test.yaml"},
        )
        assert resp.status_code == 400

    def test_execute_rejects_invalid_path(self, client):
        resp = client.post(
            "/api/v1/workflows/execute",
            json={
                "playbook_path": "/nonexistent/path.yaml",
                "alert_id": "test-001",
            },
        )
        assert resp.status_code in (400, 500)

    def test_get_status_after_execute(self, client):
        playbook_path = str(
            Path(__file__).parent.parent.parent
            / "magenta/workflows/examples/phishing-investigation.yaml"
        )
        exec_resp = client.post(
            "/api/v1/workflows/execute",
            json={
                "playbook_path": playbook_path,
                "alert_id": "status-test-001",
                "source_system": "sentinel",
            },
        )
        assert exec_resp.status_code == 200
        mission_id = exec_resp.json()["mission_id"]

        status_resp = client.get(f"/api/v1/workflows/{mission_id}/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["mission_id"] == mission_id
        assert data["status"] in ("running", "completed", "failed")

    def test_get_nodes_after_execute(self, client):
        playbook_path = str(
            Path(__file__).parent.parent.parent
            / "magenta/workflows/examples/phishing-investigation.yaml"
        )
        exec_resp = client.post(
            "/api/v1/workflows/execute",
            json={
                "playbook_path": playbook_path,
                "alert_id": "nodes-test-001",
                "source_system": "sentinel",
            },
        )
        mission_id = exec_resp.json()["mission_id"]

        nodes_resp = client.get(f"/api/v1/workflows/{mission_id}/nodes")
        assert nodes_resp.status_code == 200
        data = nodes_resp.json()
        assert data["mission_id"] == mission_id
        assert isinstance(data["nodes"], list)


# ── Approval Gate Flow ─────────────────────────────────────────────────


class TestApprovalGate:
    """Test human approval gate integration."""

    def test_approval_endpoint_returns_404_for_nonexistent(self, client):
        resp = client.post(
            "/api/v1/workflows/fake-mission/approve/fake-approval?decision=approved",
        )
        assert resp.status_code in (404, 400)

    def test_approval_requires_approver_role(self, client):
        client.headers["X-Magenta-Role"] = "viewer"
        resp = client.post(
            "/api/v1/workflows/fake-mission/approve/fake-approval?decision=approved",
        )
        assert resp.status_code == 403


# ── Playbook Validation ────────────────────────────────────────────────


class TestPlaybookValidation:
    """Test playbook validation endpoint."""

    def test_validate_v2_playbook(self, client):
        resp = client.post(
            "/api/v1/workflows/playbooks/validate",
            json={
                "apiVersion": "magenta.soar/v1",
                "kind": "Playbook",
                "metadata": {"name": "test-playbook", "version": "1.0.0"},
                "spec": {
                    "workflow": {
                        "nodes": [{"id": "node-1", "type": "ingest", "label": "Ingest"}],
                        "edges": [],
                    }
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["node_count"] == 1

    def test_validate_rejects_invalid_playbook(self, client):
        resp = client.post(
            "/api/v1/workflows/playbooks/validate",
            json={"invalid": "playbook"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False


# ── Integration: Full DAG Execution ────────────────────────────────────


class TestFullDAGExecution:
    """Integration tests for workflow compilation and DAG structure."""

    def test_compile_simple_workflow(self):
        """Test WorkflowCompiler compiles a v2 playbook into a DAG."""
        nodes = workflow_compiler.compile(playbook_v2_simple)
        assert len(nodes) == 2
        assert "step-1" in nodes
        assert "step-2" in nodes
        assert nodes["step-2"].depends_on == ["step-1"]

    def test_compile_approval_workflow(self):
        """Test compiler handles approval node type."""
        nodes = workflow_compiler.compile(playbook_v2_approval)
        assert len(nodes) == 3
        assert nodes["gate"].params["node_type"] == "approval"

    def test_compile_empty_playbook(self):
        """Test compiler handles empty workflow."""
        from magenta.core.models import PlaybookV2

        pb = PlaybookV2(
            apiVersion="magenta.soar/v1",
            kind="Playbook",
            metadata={"name": "empty", "version": "1.0.0"},
            spec={"workflow": {"nodes": [], "edges": []}},
        )
        nodes = workflow_compiler.compile(pb)
        assert len(nodes) == 0

    def test_compile_with_cycle_detects(self):
        """Test compiler detects cycles in workflow."""
        from magenta.core.models import PlaybookV2

        pb = PlaybookV2(
            apiVersion="magenta.soar/v1",
            kind="Playbook",
            metadata={"name": "cycle", "version": "1.0.0"},
            spec={
                "workflow": {
                    "nodes": [
                        {"id": "a", "type": "ingest", "label": "A"},
                        {"id": "b", "type": "agentic", "label": "B"},
                    ],
                    "edges": [
                        {"source": "a", "target": "b"},
                        {"source": "b", "target": "a"},
                    ],
                }
            },
        )
        with pytest.raises(Exception):
            workflow_compiler.compile(pb)

    def test_engine_approval_callback_mechanism(self):
        """Test that the engine approval callback resolves correctly."""
        engine = WorkflowEngine()
        engine._executions.clear()
        engine._running_missions.clear()

        mission = mission_manager.create(
            alert_id="approval-test-001",
            source_system="sentinel",
            description="Integration test",
        )

        execution = WorkflowExecution(
            mission_id=mission.mission_id,
            playbook_name="test-approval",
        )
        engine._executions[mission.mission_id] = execution

        loop = asyncio.new_event_loop()
        try:
            future = loop.create_future()
            approval_id = "test-approval-001"
            engine._approval_callbacks[approval_id] = future
            execution.approvals_pending[approval_id] = "gate"

            assert len(execution.approvals_pending) == 1
            assert approval_id in engine._approval_callbacks

            async def _test_approval():
                return await engine.respond_to_approval(approval_id, "approved")

            result = loop.run_until_complete(_test_approval())
            assert result is True
            assert future.result() == "approved"
        finally:
            loop.close()


# ── Shared playbook fixtures ───────────────────────────────────────────

playbook_v2_simple = PlaybookV2(
    apiVersion="magenta.soar/v1",
    kind="Playbook",
    metadata={"name": "test-simple", "version": "1.0.0"},
    spec={
        "workflow": {
            "nodes": [
                {"id": "step-1", "type": "ingest", "label": "Step 1"},
                {
                    "id": "step-2",
                    "type": "agentic",
                    "label": "Step 2",
                    "depends_on": ["step-1"],
                },
            ],
            "edges": [{"source": "step-1", "target": "step-2"}],
        }
    },
)

playbook_v2_approval = PlaybookV2(
    apiVersion="magenta.soar/v1",
    kind="Playbook",
    metadata={"name": "test-approval", "version": "1.0.0"},
    spec={
        "workflow": {
            "nodes": [
                {"id": "pre-approval", "type": "ingest", "label": "Pre"},
                {
                    "id": "gate",
                    "type": "approval",
                    "label": "Approval Gate",
                    "depends_on": ["pre-approval"],
                    "config": {"timeout_minutes": 5},
                },
                {
                    "id": "post-approval",
                    "type": "agentic",
                    "label": "Post",
                    "depends_on": ["gate"],
                },
            ],
            "edges": [
                {"source": "pre-approval", "target": "gate"},
                {"source": "gate", "target": "post-approval"},
            ],
        }
    },
)

# ── Integration: Concurrency Limits ────────────────────────────────────


class TestConcurrencyLimits:
    """Test agent concurrency enforcement."""

    def test_agent_respects_max_concurrent_tasks(self):
        config = AgentConfig(
            agent_id="concurrency-test-agent",
            role="analyst",
            max_concurrent_tasks=2,
        )
        agent = MockSOCAgent(config)

        assert agent.can_accept_task is True

        agent._active_tasks = 1
        assert agent.can_accept_task is True

        agent._active_tasks = 2
        assert agent.can_accept_task is False

    def test_registry_get_available_for_role(self):
        from magenta.core.agent import AgentRegistry

        agent1 = MockSOCAgent(AgentConfig(agent_id="a1", role="analyst", max_concurrent_tasks=1))
        agent2 = MockSOCAgent(AgentConfig(agent_id="a2", role="analyst", max_concurrent_tasks=2))

        registry = AgentRegistry()
        registry.register(agent1)
        registry.register(agent2)

        available = registry.get_available_for_role("analyst")
        assert len(available) == 2

        agent1._active_tasks = 1
        available = registry.get_available_for_role("analyst")
        assert len(available) == 1
        assert available[0].config.agent_id == "a2"
