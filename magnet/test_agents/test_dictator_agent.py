"""Tests for DictatorAgent — deploy/recall/halt/escalate/override/probe."""

import pytest
from datetime import datetime

from magenta.core.models import AgentConfig, SeverityLevel
from magenta.core.agent import agent_registry
from magenta.dictator.state import dictator_state
from magenta.dictator.directives import DirectiveType


class TestDictatorAgentDeploy:
    def test_deploy_triage_agent(self, dictator_with_agents):
        agent = dictator_with_agents
        import asyncio
        triage = asyncio.run(agent.deploy_agent(role="triage"))
        assert triage.role == "triage"
        assert agent_registry.get_by_id(triage.agent_id) is not None

    def test_deploy_increments_registry(self, dictator_with_agents):
        agent = dictator_with_agents
        import asyncio
        before = len(agent_registry.all_agents())
        asyncio.run(agent.deploy_agent(role="triage"))
        assert len(agent_registry.all_agents()) == before + 1

    def test_recall_agent_removes_from_registry(self, dictator_with_agents):
        agent = dictator_with_agents
        import asyncio
        triage = asyncio.run(agent.deploy_agent(role="triage"))
        assert agent_registry.get_by_id(triage.agent_id) is not None
        result = asyncio.run(agent.recall_agent(triage.agent_id))
        assert result is True
        assert agent_registry.get_by_id(triage.agent_id) is None

    def test_recall_nonexistent_returns_false(self, dictator_with_agents):
        agent = dictator_with_agents
        import asyncio
        result = asyncio.run(agent.recall_agent("nonexistent-id"))
        assert result is False


class TestDictatorMissionControl:
    def test_halt_mission_completes_oversight(self, dictator_with_agents):
        from magenta.core.models import Mission
        from magenta.core.mission import mission_manager
        import asyncio

        m = Mission(alert_id="halt-test", source_system="sentinel")
        mission_manager._missions[m.mission_id] = m
        dictator_state.track_mission(m.mission_id)

        result = asyncio.run(dictator_with_agents.halt_mission(m.mission_id, "Test halt"))
        assert result["status"] == "halted"
        assert m.mission_id not in dictator_state.active_missions

    def test_escalate_mission_changes_status(self, dictator_with_agents):
        from magenta.core.models import Mission, MissionStatus
        from magenta.core.mission import mission_manager
        import asyncio

        m = Mission(alert_id="esc-test", source_system="sentinel")
        mission_manager._missions[m.mission_id] = m

        result = asyncio.run(dictator_with_agents.escalate_mission(m.mission_id, "Test escalation"))
        assert result["status"] == "escalated"
        assert mission_manager.get(m.mission_id).status == MissionStatus.escalated

    def test_override_teaming_updates_oversight(self, dictator_with_agents):
        import asyncio

        dictator_state.track_mission("m-override", teaming="supervisor", agents=2)
        result = asyncio.run(dictator_with_agents.override_teaming("m-override", "debate"))
        assert result["teaming"] == "debate"
        assert dictator_state.active_missions["m-override"].teaming_structure == "debate"


class TestDictatorProbes:
    def test_promote_probe_creates_directive(self, dictator_with_agents):
        import asyncio
        before = len(dictator_state.directive_log)
        result = asyncio.run(dictator_with_agents.promote_probe("memory_scan", guard=True))
        assert result["probe"] == "memory_scan"
        assert len(dictator_state.directive_log) == before + 1

    def test_promote_probe_guard_flag(self, dictator_with_agents):
        import asyncio
        result = asyncio.run(dictator_with_agents.promote_probe("network_tap", guard=False))
        assert result["probe"] == "network_tap"


class TestDictatorPolicies:
    def test_apply_policy_override(self, dictator_with_agents):
        from magenta.dictator.policies import OrchestrationPolicy
        import asyncio

        policy = OrchestrationPolicy(
            name="force_mesh",
            rules={"teaming": "mesh", "trigger": {"severity_min": 1, "severity_max": 5}},
        )
        result = asyncio.run(dictator_with_agents.apply_policy_override(policy))
        assert result["status"] == "override_applied"

    def test_clear_policy_overrides(self, dictator_with_agents):
        from magenta.dictator.policies import OrchestrationPolicy
        import asyncio

        policy = OrchestrationPolicy(name="force_debate", rules={"teaming": "debate"})
        asyncio.run(dictator_with_agents.apply_policy_override(policy))
        result = asyncio.run(dictator_with_agents.clear_policy_overrides())
        assert result["status"] == "overrides_cleared"


class TestDictatorSystem:
    def test_framework_status_returns_all_sections(self, dictator_with_agents):
        import asyncio
        status = asyncio.run(dictator_with_agents.get_framework_status())
        assert "dictator" in status
        assert "registry" in status
        assert "missions" in status
        assert "policies" in status
        assert "uptime_seconds" in status

    def test_oversight_board_reflects_state(self, dictator_with_agents):
        import asyncio
        dictator_state.track_mission("m-oversight-test")
        board = asyncio.run(dictator_with_agents.get_oversight_board())
        assert "m-oversight-test" in board["active_missions"]

    def test_directive_log_returns_ordered(self, dictator_with_agents):
        import asyncio
        for i in range(5):
            dictator_state.log_directive({"type": "test", "target": f"t{i}"})
        log = asyncio.run(dictator_with_agents.get_directive_log(limit=3))
        assert len(log) == 3

    def test_system_command_creates_directive(self, dictator_with_agents):
        import asyncio
        before = len(dictator_state.directive_log)
        asyncio.run(dictator_with_agents.system_command("refresh", {"target": "registry"}))
        assert len(dictator_state.directive_log) == before + 1
