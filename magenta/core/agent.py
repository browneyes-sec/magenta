"""Agent base class and registry."""

from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4
import time

from magenta.core.models import AgentConfig, AgentStatus, Mission, AutomationActivity
from magenta.exceptions import AgentError
from magenta.config import settings
from magenta.telemetry import get_tracer, get_meter
from magenta.logging import StructuredLogger, get_structured_logger


class BaseAgent(ABC):
    """Abstract base for all Magenta agent roles."""

    _tracer = get_tracer("magenta.agent")
    _meter = get_meter("magenta.agent")

    # Prometheus metrics (class-level, shared across instances)
    _mission_duration = None
    _mission_errors = None
    _model_requests = None
    _model_errors = None
    _tool_latency = None

    @classmethod
    def _ensure_metrics(cls):
        if cls._mission_duration is None:
            cls._mission_duration = cls._meter.create_histogram(
                "magenta_mission_duration_seconds",
                description="Agent mission processing duration",
                unit="s",
            )
            cls._mission_errors = cls._meter.create_counter(
                "magenta_agent_errors_total",
                description="Agent processing errors",
            )
            cls._model_requests = cls._meter.create_counter(
                "magenta_model_requests_total",
                description="LLM model requests by agent",
            )
            cls._model_errors = cls._meter.create_counter(
                "magenta_model_errors_total",
                description="LLM model errors by agent",
            )
            cls._tool_latency = cls._meter.create_histogram(
                "magenta_tool_latency_seconds",
                description="Tool execution latency",
                unit="s",
            )

    def __init__(self, config: AgentConfig):
        self._ensure_metrics()
        self.config = config
        self.status = AgentStatus.idle
        self.current_mission: Optional[Mission] = None
        self.turn_count = 0
        self.started_at: Optional[datetime] = None
        self._heartbeat_count = 0
        self._active_tasks = 0
        self._pre_turn_rag: bool = True  # Enable pre-turn RAG by default (ADR-018)
        self._logger = StructuredLogger(
            get_structured_logger(f"magenta.agent.{config.role}"),
            agent_id=config.agent_id,
        )

    @property
    def can_accept_task(self) -> bool:
        """Check if agent can accept another concurrent task."""
        return self._active_tasks < self.config.max_concurrent_tasks

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
    async def _process_impl(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        """Process a mission task and return results. Override in subclasses."""

    async def process(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        """Wrap _process_impl with OTel tracing and metrics."""
        start = time.monotonic()
        mission_id = mission.mission_id if hasattr(mission, "mission_id") else ""
        correlation_id = mission.correlation_id if hasattr(mission, "correlation_id") else ""

        self._logger = self._logger.bind(
            mission_id=mission_id,
            correlation_id=correlation_id,
        )

        with self._tracer.start_as_current_span(
            f"agent.{self.role}.process",
            attributes={
                "mission.id": mission_id,
                "mission.severity": getattr(mission, "severity", ""),
                "mission.risk_score": getattr(mission, "risk_score", 0),
                "agent.id": self.agent_id,
                "agent.role": self.role,
                "agent.model": self.config.model_name,
            },
        ) as span:
            try:
                self._active_tasks += 1
                self.status = AgentStatus.executing
                self.current_mission = mission
                self.turn_count += 1
                self._logger.info(f"Agent {self.role} processing mission")

                # Pre-turn RAG: retrieve relevant context from memory (ADR-018)
                if self._pre_turn_rag and hasattr(self, "retrieve_context"):
                    try:
                        rag_context = await self.retrieve_context(
                            query_summary=mission.description[:200],
                            mission_id=mission.mission_id if hasattr(mission, "mission_id") else "",
                            tenant_id=context.get("tenant_id", "default"),
                        )
                        context["rag_context"] = rag_context
                    except Exception as rag_exc:
                        self._logger.warning(f"Pre-turn RAG failed: {rag_exc}")
                        context["rag_context"] = ""

                result = await self._process_impl(mission, context)
                span.set_status(1)  # OK
                self._logger.info(f"Agent {self.role} completed mission", action="process", status="succeeded")

                # Post-turn: auto-log activity to episodic memory (ADR-018)
                if hasattr(self, "log_activity"):
                    try:
                        from magenta.core.models import ActionStatus
                        await self.log_activity(
                            mission=mission,
                            action=f"{self.role}_completed",
                            status=ActionStatus.succeeded,
                            tenant_id=context.get("tenant_id", "default"),
                        )
                    except Exception as log_exc:
                        self._logger.warning(f"Post-turn log_activity failed: {log_exc}")

                return result
            except Exception as exc:
                span.set_status(2, str(exc))  # ERROR
                self._mission_errors.add(1, {"role": self.role, "error": type(exc).__name__})
                self._logger.error(f"Agent {self.role} failed: {exc}", action="process", status="failed")
                raise
            finally:
                elapsed = time.monotonic() - start
                self._mission_duration.record(elapsed, {"role": self.role})
                self._active_tasks = max(0, self._active_tasks - 1)
                if self._active_tasks == 0:
                    self.status = AgentStatus.idle
                    self.current_mission = None

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        """Execute a tool by name with latency metrics. Override in subclasses."""
        start = time.monotonic()
        is_llm = tool_name.startswith("llm_") or tool_name.startswith("model_")
        try:
            if is_llm:
                self._model_requests.add(1, {"role": self.role, "tool": tool_name})
            result = await self._execute_tool_impl(tool_name, params)
            return result
        except Exception as exc:
            if is_llm:
                self._model_errors.add(1, {"role": self.role, "tool": tool_name, "error": type(exc).__name__})
            raise
        finally:
            elapsed = time.monotonic() - start
            self._tool_latency.record(elapsed, {"role": self.role, "tool": tool_name})

    async def _execute_tool_impl(self, tool_name: str, params: dict[str, Any]) -> Any:
        """Tool execution logic. Override in subclasses."""
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

    def get_available_for_role(self, role: str) -> list[BaseAgent]:
        """Return agents for role that can accept more concurrent tasks."""
        return [
            a for a in self._agents.get(role, [])
            if a.can_accept_task
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
