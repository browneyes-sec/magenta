"""Tests for LangGraph subgraph registry and pre-built SOC subgraphs."""

from __future__ import annotations

import pytest

from magenta.workflows.langgraph.engine import (
    HAS_LANGGRAPH,
    WorkflowState,
    build_compliance_subgraph,
    build_containment_subgraph,
    build_investigation_subgraph,
    build_triage_subgraph,
    get_subgraph,
    initialize_subgraphs,
    list_subgraphs,
)


@pytest.fixture(autouse=True)
def _init_subgraphs():
    initialize_subgraphs()


class TestLangGraphSubgraphs:
    def test_has_langgraph(self):
        assert HAS_LANGGRAPH is True

    def test_list_subgraphs(self):
        names = list_subgraphs()
        assert len(names) >= 4
        assert "triage_subgraph" in names
        assert "investigation_subgraph" in names
        assert "containment_subgraph" in names
        assert "compliance_subgraph" in names

    def test_get_subgraph(self):
        graph = get_subgraph("triage_subgraph")
        assert graph is not None

    def test_get_nonexistent(self):
        graph = get_subgraph("nonexistent")
        assert graph is None

    def test_triage_compiled(self):
        graph = get_subgraph("triage_subgraph")
        assert hasattr(graph, "invoke") or hasattr(graph, "ainvoke")

    def test_investigation_compiled(self):
        graph = get_subgraph("investigation_subgraph")
        assert graph is not None

    def test_containment_compiled(self):
        graph = get_subgraph("containment_subgraph")
        assert graph is not None

    def test_compliance_compiled(self):
        graph = get_subgraph("compliance_subgraph")
        assert graph is not None

    def test_workflow_state_fields(self):
        state = WorkflowState(
            messages=[],
            alert_id="test-123",
            mission_id="mission-001",
            context={},
        )
        assert state["alert_id"] == "test-123"
        assert state["mission_id"] == "mission-001"

    def test_build_triage_subgraph(self):
        graph = build_triage_subgraph()
        assert graph is not None
        assert hasattr(graph, "invoke") or hasattr(graph, "ainvoke")

    def test_build_investigation_subgraph(self):
        graph = build_investigation_subgraph()
        assert graph is not None

    def test_build_containment_subgraph(self):
        graph = build_containment_subgraph()
        assert graph is not None

    def test_build_compliance_subgraph(self):
        graph = build_compliance_subgraph()
        assert graph is not None
