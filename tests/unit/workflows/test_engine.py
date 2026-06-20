"""Tests for WorkflowEngine — DAG execution with approvals, decisions, parallel."""
from __future__ import annotations

import pytest

from magenta.core.models import PlaybookV2
from magenta.workflows.compiler import WorkflowCompiler
from magenta.workflows.engine import WorkflowEngine


@pytest.fixture
def compiler():
    return WorkflowCompiler()


@pytest.fixture
def simple_playbook():
    return PlaybookV2(
        apiVersion="magenta.soar/v1",
        kind="Playbook",
        metadata={"name": "simple-test", "version": "1.0.0", "description": "Simple test"},
        spec={
            "workflow": {
                "nodes": [
                    {"id": "n1", "type": "ingest", "label": "N1"},
                    {"id": "n2", "type": "agentic", "label": "N2"},
                ],
                "edges": [{"source": "n1", "target": "n2"}],
            }
        },
    )


@pytest.fixture
def approval_playbook():
    return PlaybookV2(
        apiVersion="magenta.soar/v1",
        kind="Playbook",
        metadata={"name": "approval-test", "version": "1.0.0", "description": "Approval test"},
        spec={
            "workflow": {
                "nodes": [
                    {"id": "start", "type": "ingest", "label": "Start"},
                    {
                        "id": "gate",
                        "type": "approval",
                        "label": "Approval Gate",
                        "config": {"timeout_seconds": 300},
                    },
                    {"id": "after", "type": "agentic", "label": "After"},
                ],
                "edges": [
                    {"source": "start", "target": "gate"},
                    {"source": "gate", "target": "after"},
                ],
            }
        },
    )


class TestWorkflowEngine:
    def test_initialization(self):
        engine = WorkflowEngine()
        assert engine._executions == {}
        assert engine._approval_callbacks == {}

    def test_compile_and_get_status(self, compiler, simple_playbook):
        dag = compiler.compile(simple_playbook)
        assert len(dag) == 2
        assert "n1" in dag
        assert "n2" in dag

    def test_get_execution_status_none(self):
        engine = WorkflowEngine()
        assert engine.get_execution_status("nonexistent") is None

    def test_approval_playbook_has_approval_node(self, compiler, approval_playbook):
        dag = compiler.compile(approval_playbook)
        assert "gate" in dag
        assert dag["gate"].role == "approval"
