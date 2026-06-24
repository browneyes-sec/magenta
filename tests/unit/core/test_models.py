"""Tests for core domain models: Mission, Playbook, PlaybookV2, WorkflowSpec."""

from __future__ import annotations

import pytest
from datetime import datetime
from uuid import uuid4

from magenta.core.models import (
    AgentConfig,
    AgentStatus,
    Mission,
    MissionStatus,
    Playbook,
    PlaybookV2,
    SourceSystem,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeType,
    WorkflowSpec,
)


class TestMission:
    def test_create_mission(self):
        m = Mission(
            alert_id="alert-001",
            source_system="sentinel",
            description="Phishing test",
        )
        assert m.alert_id == "alert-001"
        assert m.status == MissionStatus.created
        assert m.mission_id  # auto-generated UUID

    def test_mission_default_timestamps(self):
        m = Mission(alert_id="a", source_system="sentinel")
        assert isinstance(m.created_at, datetime)
        assert isinstance(m.updated_at, datetime)

    def test_mission_artifact_bundle_default(self):
        m = Mission(alert_id="a", source_system="sentinel")
        assert m.artifact_bundle == {}

    def test_mission_team_default(self):
        m = Mission(alert_id="a", source_system="sentinel")
        assert m.team == []

    def test_mission_tasks_default(self):
        m = Mission(alert_id="a", source_system="sentinel")
        assert m.tasks == []


class TestPlaybook:
    def test_create_playbook(self):
        pb = Playbook(name="phishing", version="1.0.0", stages=[])
        assert pb.name == "phishing"
        assert pb.version == "1.0.0"

    def test_playbook_stages(self):
        pb = Playbook(
            name="test",
            version="1.0.0",
            stages=[{"name": "triage", "steps": []}],
        )
        assert len(pb.stages) == 1


class TestWorkflowSpec:
    def test_workflow_node_types(self):
        for nt in WorkflowNodeType:
            assert isinstance(nt.value, str)

    def test_create_workflow_node(self):
        node = WorkflowNode(
            id="node-1",
            type=WorkflowNodeType.ingest,
            label="Ingest Alert",
        )
        assert node.id == "node-1"
        assert node.type == WorkflowNodeType.ingest

    def test_create_workflow_edge(self):
        edge = WorkflowEdge(source="node-1", target="node-2")
        assert edge.source == "node-1"
        assert edge.target == "node-2"


class TestPlaybookV2:
    def test_create_playbook_v2(self):
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="n1", type=WorkflowNodeType.ingest, label="Ingest"),
                WorkflowNode(id="n2", type=WorkflowNodeType.agentic, label="Triage"),
            ],
            edges=[WorkflowEdge(source="n1", target="n2")],
        )
        pb = PlaybookV2(
            apiVersion="v2",
            kind="Playbook",
            metadata={"name": "test"},
            spec=spec,
        )
        assert pb.apiVersion == "v2"
        assert pb.kind == "Playbook"
        assert len(pb.spec.nodes) == 2


class TestAgentConfig:
    def test_agent_config_defaults(self):
        config = AgentConfig(agent_id="a1", role="triage")
        assert config.agent_id == "a1"
        assert config.role == "triage"

    def test_agent_status_enum(self):
        assert AgentStatus.active.value == "active"
        assert AgentStatus.busy.value == "busy"
        assert AgentStatus.offline.value == "offline"


class TestMissionStatus:
    def test_all_statuses_exist(self):
        statuses = [s.value for s in MissionStatus]
        assert "created" in statuses
        assert "executing" in statuses
        assert "completed" in statuses
        assert "failed" in statuses
        assert "cancelled" in statuses
