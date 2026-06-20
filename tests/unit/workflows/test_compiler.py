"""Tests for WorkflowCompiler — YAML/Graph → DAG compilation."""
from __future__ import annotations

import tempfile

import pytest

from magenta.core.models import PlaybookV2, WorkflowNodeType
from magenta.workflows.compiler import WorkflowCompiler


@pytest.fixture
def compiler():
    return WorkflowCompiler()


@pytest.fixture
def sample_playbook():
    return PlaybookV2(
        apiVersion="magenta.soar/v1",
        kind="Playbook",
        metadata={
            "name": "test-playbook",
            "version": "1.0.0",
            "description": "Test",
            "owner": "test",
        },
        spec={
            "workflow": {
                "nodes": [
                    {
                        "id": "ingest-1",
                        "type": "ingest",
                        "label": "Ingest Alert",
                        "config": {"source": "sentinel"},
                    },
                    {
                        "id": "analyze-1",
                        "type": "agentic",
                        "label": "Analyze",
                        "config": {"agent": "triage-agent"},
                    },
                    {
                        "id": "decision-1",
                        "type": "decision",
                        "label": "Classify",
                        "config": {"conditions": {"sev_high": True}},
                    },
                ],
                "edges": [
                    {"source": "ingest-1", "target": "analyze-1"},
                    {"source": "analyze-1", "target": "decision-1"},
                ],
            }
        },
    )


class TestWorkflowCompiler:
    def test_compile_from_playbook(self, compiler, sample_playbook):
        dag = compiler.compile(sample_playbook)
        assert len(dag) == 3
        assert "ingest-1" in dag
        assert "analyze-1" in dag
        assert "decision-1" in dag
        assert dag["analyze-1"].depends_on == ["ingest-1"]
        assert dag["decision-1"].depends_on == ["analyze-1"]

    def test_compile_from_yaml_file(self, compiler):
        yaml_content = """\
apiVersion: "magenta.soar/v1"
kind: Playbook
metadata:
  name: yaml-test
  version: "1.0.0"
  description: YAML test playbook
  owner: test
spec:
  workflow:
    nodes:
      - id: n1
        type: ingest
        label: Node 1
        config: {source: sentinel}
      - id: n2
        type: agentic
        label: Node 2
        config: {agent: triage}
    edges:
      - source: n1
        target: n2
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            pb = compiler.load_playbook(f.name)
            dag = compiler.compile(pb)
            assert len(dag) == 2
            assert dag["n2"].depends_on == ["n1"]

    def test_cycle_detection(self, compiler):
        playbook = PlaybookV2(
            apiVersion="magenta.soar/v1",
            kind="Playbook",
            metadata={"name": "cycle-test"},
            spec={
                "workflow": {
                    "nodes": [
                        {"id": "a", "type": "ingest", "label": "A"},
                        {"id": "b", "type": "ingest", "label": "B"},
                    ],
                    "edges": [
                        {"source": "a", "target": "b"},
                        {"source": "b", "target": "a"},
                    ],
                }
            },
        )
        with pytest.raises(Exception):
            compiler.compile(playbook)

    def test_empty_workflow(self, compiler):
        playbook = PlaybookV2(
            apiVersion="magenta.soar/v1",
            kind="Playbook",
            metadata={"name": "empty"},
            spec={"workflow": {"nodes": [], "edges": []}},
        )
        dag = compiler.compile(playbook)
        assert len(dag) == 0

    def test_parallel_branches(self, compiler):
        playbook = PlaybookV2(
            apiVersion="magenta.soar/v1",
            kind="Playbook",
            metadata={"name": "parallel-test"},
            spec={
                "workflow": {
                    "nodes": [
                        {"id": "start", "type": "ingest", "label": "Start"},
                        {"id": "branch1", "type": "agentic", "label": "B1"},
                        {"id": "branch2", "type": "agentic", "label": "B2"},
                        {"id": "join", "type": "decision", "label": "Join"},
                    ],
                    "edges": [
                        {"source": "start", "target": "branch1"},
                        {"source": "start", "target": "branch2"},
                        {"source": "branch1", "target": "join"},
                        {"source": "branch2", "target": "join"},
                    ],
                }
            },
        )
        dag = compiler.compile(playbook)
        join_node = dag["join"]
        assert set(join_node.depends_on) == {"branch1", "branch2"}

    def test_node_type_handlers(self, compiler):
        expected_types = {
            WorkflowNodeType.ingest,
            WorkflowNodeType.agentic,
            WorkflowNodeType.decision,
            WorkflowNodeType.approval,
            WorkflowNodeType.action,
            WorkflowNodeType.publisher,
            WorkflowNodeType.parallel,
            WorkflowNodeType.subgraph,
        }
        assert set(compiler._node_type_handlers.keys()) == expected_types
