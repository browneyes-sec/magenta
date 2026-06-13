"""Agent base class and registry."""

from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from magenta.core.models import AgentConfig, AgentStatus, Mission, AutomationActivity
from magenta.exceptions import AgentError
from magenta.config import settings


class BaseAgent(ABC):
    """Abstract base for all Magenta agent roles."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.status = AgentStatus.idle
        self.current_mission: Optional[Mission] = None
        self.turn_count = 0
        self.started_at: Optional[datetime] = None
        self._heartbeat_count = 0

    @property
    def agent_id(self) -> str:
        return self.config.agent_id

    @property
    def role(self) -> str:
        return self.config.role

    async def initialize(self) -> None:
        """Called when agent is registered and ready."""
        self.status = AgentStatus.idle

    @abstractmethod
    async def process(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        """Process a mission task and return results."""

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        """Execute a tool by name. Override in subclasses."""
        raise NotImplementedError(f"Tool {tool_name} not implemented in {self.role}")

    async def heartbeat(self) -> dict[str, Any]:
        """Return agent health status."""
        self._heartbeat_count += 1
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "status": self.status.value,
            "uptime_seconds": (
                (datetime.utcnow() - self.started_at).total_seconds()
                if self.started_at else 0
            ),
            "turn_count": self.turn_count,
        }

    def reset(self) -> None:
        """Reset agent state for new mission."""
        self.status = AgentStatus.idle
        self.current_mission = None
        self.turn_count = 0
        self.started_at = None


class AgentRegistry:
    """Registry of all available agents, keyed by role."""

    def __init__(self):
        self._agents: dict[str, list[BaseAgent]] = {}

    def register(self, agent: BaseAgent) -> None:
        role = agent.role
        if role not in self._agents:
            self._agents[role] = []
        self._agents[role].append(agent)

    def unregister(self, agent_id: str) -> None:
        for role, agents in self._agents.items():
            self._agents[role] = [a for a in agents if a.agent_id != agent_id]

    def get_by_role(self, role: str) -> list[BaseAgent]:
        return self._agents.get(role, [])

    def get_by_id(self, agent_id: str) -> Optional[BaseAgent]:
        for agents in self._agents.values():
            for agent in agents:
                if agent.agent_id == agent_id:
                    return agent
        return None

    def get_available(self, role: str) -> list[BaseAgent]:
        return [
            a for a in self._agents.get(role, [])
            if a.status == AgentStatus.idle
        ]

    def all_agents(self) -> list[BaseAgent]:
        result = []
        for agents in self._agents.values():
            result.extend(agents)
        return result

    @property
    def counts(self) -> dict[str, int]:
        return {role: len(agents) for role, agents in self._agents.items()}


agent_registry = AgentRegistry()
