"""Shared fixtures for the Magenta test suite.

Provides mock agents, missions, and framework state that can be
used across all test modules without external dependencies.
"""

from typing import Any
from uuid import uuid4

import pytest

from magenta.agents.dictator import DictatorAgent
from magenta.core.agent import BaseAgent, agent_registry
from magenta.core.mission import mission_manager
from magenta.core.models import (
    AgentConfig,
    Mission,
    SeverityLevel,
)
from magenta.dictator.policies import policy_engine
from magenta.dictator.state import DictatorStatus, dictator_state

# ── Mock Agent ────────────────────────────────────────────────────


class MockAgent(BaseAgent):
    """A minimal agent that returns canned responses for testing."""

    def __init__(self, role: str, agent_id: str | None = None):
        config = AgentConfig(
            agent_id=agent_id or f"mock-{role}-{uuid4().hex[:6]}",
            role=role,
        )
        super().__init__(config)
        self.last_mission = None
        self.last_context = None
        self._process_result = {"status": "ok", "data": "mock-processed"}

    async def process(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        self.last_mission = mission
        self.last_context = context
        self.turn_count += 1
        return self._process_result


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def reset_state():
    """Reset all global state before each test."""
    # Reset Dictator state
    dictator_state.active_missions.clear()
    dictator_state.completed_missions.clear()
    dictator_state.directive_log.clear()
    dictator_state.status = DictatorStatus.idle

    # Reset agent registry
    for agent in list(agent_registry.all_agents()):
        agent_registry.unregister(agent.agent_id)

    # Reset mission manager state
    mission_manager._missions.clear()

    # Reset policy overrides
    await policy_engine.clear_overrides()

    yield


@pytest.fixture
def sample_mission() -> Mission:
    """Create a basic mission for testing."""
    return Mission(
        alert_id="test-alert-001",
        source_system="sentinel",
        severity=SeverityLevel.medium,
        risk_score=45,
        description="Test mission for unit tests",
    )


@pytest.fixture
def high_severity_mission() -> Mission:
    """Create a high-severity mission that triggers debate teaming."""
    return Mission(
        alert_id="test-alert-critical",
        source_system="sentinel",
        severity=SeverityLevel.high,
        risk_score=78,
        description="Critical test mission for policy evaluation",
    )


@pytest.fixture
def critical_mission() -> Mission:
    """Create a critical mission that triggers referee teaming."""
    return Mission(
        alert_id="test-alert-critical-999",
        source_system="sentinel",
        severity=SeverityLevel.critical,
        risk_score=92,
        description="Critical severity mission for referee policy tests",
    )


@pytest.fixture
def mock_triage_agent() -> MockAgent:
    """Register and return a mock triage agent."""
    agent = MockAgent(role="triage")
    agent_registry.register(agent)
    return agent


@pytest.fixture
def mock_swarm_manager() -> MockAgent:
    """Register and return a mock swarm manager."""
    agent = MockAgent(role="swarm_manager")
    agent_registry.register(agent)
    return agent


@pytest.fixture
def registered_missions(mock_swarm_manager, mock_triage_agent) -> list[Mission]:
    """Create and register several missions in the manager."""
    missions = []
    for i in range(3):
        m = Mission(
            alert_id=f"bulk-alert-{i:03d}",
            source_system="splunk",
            severity=SeverityLevel(i % 5 + 1),
            risk_score=20 + i * 15,
            description=f"Bulk test mission {i}",
        )
        mission_manager._missions[m.mission_id] = m
        missions.append(m)
    return missions


@pytest.fixture
def dictator_with_agents() -> DictatorAgent:
    """Return a DictatorAgent with mock triage and swarm_manager registered."""
    agent_registry.register(MockAgent(role="triage"))
    agent_registry.register(MockAgent(role="swarm_manager"))
    from magenta.agents.dictator import dictator as d

    return d
