"""Tests for critical fixes: safe_eval, mission state machine, playbook versioning."""

from __future__ import annotations

import asyncio

import pytest

from magenta.core.agent import BaseAgent
from magenta.core.mission import _VALID_TRANSITIONS, MissionManager
from magenta.core.models import AgentConfig, MissionStatus, Playbook
from magenta.core.playbook import PlaybookManager
from magenta.exceptions import MissionError, MissionNotFoundError
from magenta.models.router import CircuitBreaker


class TestSafeEval:
    def test_simple_comparison(self):
        from magenta.workflows.engine import _safe_eval

        assert _safe_eval("1 == 1", {}) is True
        assert _safe_eval("1 != 1", {}) is False

    def test_variable_lookup(self):
        from magenta.workflows.engine import _safe_eval

        assert _safe_eval("x > 5", {"x": 10}) is True
        assert _safe_eval("x > 5", {"x": 3}) is False

    def test_boolean_operators(self):
        from magenta.workflows.engine import _safe_eval

        assert _safe_eval("a and b", {"a": True, "b": True}) is True
        assert _safe_eval("a and b", {"a": True, "b": False}) is False
        assert _safe_eval("a or b", {"a": False, "b": True}) is True

    def test_not_operator(self):
        from magenta.workflows.engine import _safe_eval

        assert _safe_eval("not x", {"x": False}) is True
        assert _safe_eval("not x", {"x": True}) is False

    def test_string_comparison(self):
        from magenta.workflows.engine import _safe_eval

        assert _safe_eval('status == "high"', {"status": "high"}) is True
        assert _safe_eval('status == "high"', {"status": "low"}) is False

    def test_in_operator(self):
        from magenta.workflows.engine import _safe_eval

        assert _safe_eval("x in items", {"x": 1, "items": [1, 2, 3]}) is True
        assert _safe_eval("x not in items", {"x": 4, "items": [1, 2, 3]}) is True

    def test_attribute_access(self):
        from magenta.workflows.engine import _safe_eval

        class Obj:
            severity = "high"

        assert _safe_eval("obj.severity == 'high'", {"obj": Obj()}) is True

    def test_subscript_access(self):
        from magenta.workflows.engine import _safe_eval

        assert _safe_eval('data["key"] == 1', {"data": {"key": 1}}) is True

    def test_rejects_function_calls(self):
        from magenta.workflows.engine import _safe_eval

        with pytest.raises(ValueError, match="Function calls not allowed"):
            _safe_eval("__import__('os').system('ls')", {})

    def test_rejects_unknown_variable(self):
        from magenta.workflows.engine import _safe_eval

        with pytest.raises(ValueError, match="Unknown variable"):
            _safe_eval("unknown_var", {})

    def test_rejects_unsupported_node(self):
        from magenta.workflows.engine import _safe_eval

        with pytest.raises(ValueError, match="Unsupported expression"):
            _safe_eval("lambda x: x", {})


class TestMissionStateMachine:
    def test_valid_transition(self):
        mm = MissionManager()
        m = mm.create(alert_id="a", source_system="sentinel")
        assert m.status == MissionStatus.created
        mm.update_status(m.mission_id, MissionStatus.executing)
        assert m.status == MissionStatus.executing

    def test_invalid_transition_raises(self):
        mm = MissionManager()
        m = mm.create(alert_id="a", source_system="sentinel")
        mm.update_status(m.mission_id, MissionStatus.executing)
        mm.update_status(m.mission_id, MissionStatus.completed)
        with pytest.raises(MissionError, match="Invalid transition"):
            mm.update_status(m.mission_id, MissionStatus.executing)

    def test_terminal_states_cannot_transition(self):
        mm = MissionManager()
        m = mm.create(alert_id="a", source_system="sentinel")
        mm.update_status(m.mission_id, MissionStatus.executing)
        mm.update_status(m.mission_id, MissionStatus.completed)
        with pytest.raises(MissionError):
            mm.update_status(m.mission_id, MissionStatus.failed)

    def test_cannot_delete_executing_mission(self):
        mm = MissionManager()
        m = mm.create(alert_id="a", source_system="sentinel")
        mm.update_status(m.mission_id, MissionStatus.executing)
        with pytest.raises(MissionError, match="Cannot delete"):
            mm.delete(m.mission_id)

    def test_can_delete_completed_mission(self):
        mm = MissionManager()
        m = mm.create(alert_id="a", source_system="sentinel")
        mm.update_status(m.mission_id, MissionStatus.executing)
        mm.update_status(m.mission_id, MissionStatus.completed)
        mm.delete(m.mission_id)
        with pytest.raises(MissionNotFoundError):
            mm.get(m.mission_id)

    def test_list_active(self):
        mm = MissionManager()
        m1 = mm.create(alert_id="a1", source_system="sentinel")
        m2 = mm.create(alert_id="a2", source_system="sentinel")
        mm.update_status(m1.mission_id, MissionStatus.executing)
        mm.update_status(m2.mission_id, MissionStatus.executing)
        mm.update_status(m1.mission_id, MissionStatus.completed)
        active = mm.list_active()
        assert len(active) == 1
        assert active[0].mission_id == m2.mission_id

    def test_all_transitions_defined(self):
        for status in MissionStatus:
            assert status in _VALID_TRANSITIONS


class TestPlaybookVersioning:
    def test_get_returns_latest_version(self):
        pm = PlaybookManager()
        pb1 = Playbook(name="test", version="1.0.0", stages=[])
        pb2 = Playbook(name="test", version="2.0.0", stages=[])
        pm.register(pb1)
        pm.register(pb2)
        result = pm.get("test")
        assert result is not None
        assert result.version == "2.0.0"

    def test_get_specific_version(self):
        pm = PlaybookManager()
        pb1 = Playbook(name="test", version="1.0.0", stages=[])
        pb2 = Playbook(name="test", version="2.0.0", stages=[])
        pm.register(pb1)
        pm.register(pb2)
        result = pm.get("test", version="1.0.0")
        assert result is not None
        assert result.version == "1.0.0"

    def test_get_nonexistent(self):
        pm = PlaybookManager()
        assert pm.get("nonexistent") is None


class TestMaxConcurrentTasks:
    def test_agent_can_accept_task_respects_limit(self):
        config = AgentConfig(
            agent_id="test-agent-1",
            role="analyst",
            max_concurrent_tasks=2,
        )

        class TestAgent(BaseAgent):
            async def _process_impl(self, mission, context):
                return {"status": "done"}

            async def _execute_tool_impl(self, tool_name, params):
                return None

        agent = TestAgent(config)
        assert agent.can_accept_task is True

        agent._active_tasks = 1
        assert agent.can_accept_task is True

        agent._active_tasks = 2
        assert agent.can_accept_task is False

    def test_registry_get_available_for_role(self):
        config1 = AgentConfig(
            agent_id="agent-1",
            role="analyst",
            max_concurrent_tasks=1,
        )
        config2 = AgentConfig(
            agent_id="agent-2",
            role="analyst",
            max_concurrent_tasks=2,
        )

        class TestAgent(BaseAgent):
            async def _process_impl(self, mission, context):
                return {"status": "done"}

            async def _execute_tool_impl(self, tool_name, params):
                return None

        agent1 = TestAgent(config1)
        agent2 = TestAgent(config2)

        # Create fresh registry to avoid pollution
        from magenta.core.agent import AgentRegistry

        test_registry = AgentRegistry()
        test_registry.register(agent1)
        test_registry.register(agent2)

        # Both available initially
        available = test_registry.get_available_for_role("analyst")
        assert len(available) == 2

        # Fill agent1 to capacity
        agent1._active_tasks = 1
        available = test_registry.get_available_for_role("analyst")
        assert len(available) == 1
        assert available[0].agent_id == "agent-2"

        # Fill agent2 to capacity
        agent2._active_tasks = 2
        available = test_registry.get_available_for_role("analyst")
        assert len(available) == 0


class TestCircuitBreaker:
    def test_circuit_opens_at_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)

        # After 2 failures, still closed
        cb.record_failure("test-client")
        cb.record_failure("test-client")
        assert cb.is_open("test-client") is False

        # 3rd failure opens circuit
        cb.record_failure("test-client")
        assert cb.is_open("test-client") is True

    def test_circuit_closes_on_success(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=60.0)

        cb.record_failure("test-client")
        cb.record_failure("test-client")
        assert cb.is_open("test-client") is True

        cb.record_success("test-client")
        assert cb.is_open("test-client") is False

    def test_cooldown_expires(self):
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)

        cb.record_failure("test-client")
        assert cb.is_open("test-client") is True

        import time

        time.sleep(0.02)
        assert cb.is_open("test-client") is False


class TestGracefulShutdown:
    def test_workflow_engine_shutdown_no_running(self):
        from magenta.workflows.engine import WorkflowEngine

        engine = WorkflowEngine()
        asyncio.run(engine.shutdown(timeout_seconds=1.0))
        # Should complete without error

    def test_workflow_engine_shutdown_with_running(self):
        from magenta.workflows.engine import WorkflowEngine

        engine = WorkflowEngine()
        engine._running_missions.add("mission-1")
        # Shutdown with short timeout - should wait and then give up
        asyncio.run(engine.shutdown(timeout_seconds=0.1))
        # Should still complete (timed out but didn't hang)
