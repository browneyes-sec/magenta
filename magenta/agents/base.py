"""Base agent with LLM + tool execution loop."""

from abc import ABC
from typing import Any

from magenta.core.agent import BaseAgent
from magenta.core.models import ActionStatus, AgentConfig, AutomationActivity, Mission
from magenta.models.base import ModelRequest, ModelResponse
from magenta.models.router import model_router

USE_GATEWAY = True

try:
    from magenta.gateway.engine import LLMGateway
    _gateway = LLMGateway()
except ImportError:
    _gateway = None
    USE_GATEWAY = False


class LLMAgent(BaseAgent, ABC):
    """Agent that uses an LLM for reasoning and tool use."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.system_prompt = self._build_system_prompt()
        self.sensitivity_level: str = "low"
        self.task_type: str = "generic"

    def _build_system_prompt(self) -> str:
        role = self.config.role
        tools = ", ".join(self.config.tools)
        return self.config.instructions or (
            f"You are a {role} agent in a SOC environment.\n"
            f"You have access to the following tools: {tools}.\n"
            "Always reason step by step. Log all findings."
        )

    def _resolve_sensitivity(self) -> str:
        return getattr(self, "sensitivity_level", "low")

    def _resolve_priority(self) -> str:
        return getattr(self, "priority", "interactive")

    def _resolve_task_type(self) -> str:
        return getattr(self, "task_type", "generic")

    def _get_redaction_policy(self) -> dict | None:
        return None

    async def llm_generate(
        self,
        prompt: str,
        tier: str = "speed",
        temperature: float = 0.2,
    ) -> ModelResponse:
        request = ModelRequest(
            messages=[{"role": "user", "content": prompt}],
            system=self.system_prompt,
            temperature=temperature,
            correlation_id="",
            task_type=self._resolve_task_type(),
            sensitivity_level=self._resolve_sensitivity(),
            priority=self._resolve_priority(),
            redaction_policy=self._get_redaction_policy(),
        )

        if USE_GATEWAY and _gateway:
            return await _gateway.route(request)

        return await model_router.route(request, tier=tier)

    async def log_activity(self, mission: Mission, action: str, status: ActionStatus) -> None:
        """Log action to episodic memory and registry."""
        activity = AutomationActivity(
            source_system=mission.source_system,
            source_alert_id=mission.alert_id,
            playbook_id=mission.playbook_id,
            action=action,
            status=status,
            correlation_id=mission.correlation_id,
            executor={"type": "agent", "id": self.agent_id},
        )

        try:
            from magenta.mesh.memory import memory_mcp

            await memory_mcp.write_episode(
                agent_role=self.config.role,
                mission_id=mission.mission_id,
                turn_number=self.turn_count,
                text=f"Action: {action} | Status: {status.value} | Alert: {mission.alert_id}",
                correlation_id=mission.correlation_id,
                metadata={
                    "activity_id": activity.event_id,
                    "playbook_id": mission.playbook_id,
                    "source_system": mission.source_system.value,
                    "action_type": (
                        activity.action.value
                        if hasattr(activity.action, "value")
                        else str(activity.action)
                    ),
                },
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Failed to write episodic memory")

        return None

    async def heartbeat(self) -> dict[str, Any]:
        base = await super().heartbeat()
        base["model"] = f"{self.config.model_provider}/{self.config.model_name}"
        base["system_prompt_length"] = len(self.system_prompt)
        return base
