"""Base agent with LLM + tool execution loop."""

from abc import ABC
from typing import Any

from magenta.core.agent import BaseAgent
from magenta.core.models import ActionStatus, AgentConfig, AutomationActivity, Mission
from magenta.models.base import ModelRequest, ModelResponse
from magenta.models.router import model_router

# Token budgets per tier (ADR-018 §3.2)
TIER_TOKEN_BUDGETS = {
    "speed": 1000,
    "reasoning": 3000,
    "cost_save": 500,
}

USE_GATEWAY = True

try:
    from magenta.gateway.engine import LLMGateway

    _gateway = LLMGateway()
except ImportError:
    _gateway = None
    USE_GATEWAY = False

try:
    from magenta.config import settings
    from magenta.gateway.redact import RedactionLayer

    _redact_layer = RedactionLayer(
        enabled=settings.gateway.redaction.enabled,
        default_fields=settings.gateway.redaction.default_fields,
    )
except Exception:
    _redact_layer = None

try:
    from magenta.core.conversation import conversation_manager
except Exception:
    conversation_manager = None


class LLMAgent(BaseAgent, ABC):
    """Agent that uses an LLM for reasoning and tool use."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.system_prompt = self._build_system_prompt()
        self.sensitivity_level: str = "low"
        self.task_type: str = "generic"
        self._session_id: str | None = None

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
        session_id: str = "",
        include_history: bool = True,
    ) -> ModelResponse:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt.
            tier: Model tier (speed, reasoning, cost_save).
            temperature: Sampling temperature.
            session_id: Optional session ID for multi-turn conversations.
            include_history: Include conversation history in context.
        """
        messages = [{"role": "user", "content": prompt}]

        if include_history and session_id and conversation_manager:
            session = conversation_manager.get_or_create(
                session_id=session_id,
                agent_role=self.config.role,
            )
            session.add_user_message(prompt)
            history = session.get_context_messages()
            if len(history) > 1:
                messages = history

        request = ModelRequest(
            messages=messages,
            system=self.system_prompt,
            temperature=temperature,
            correlation_id="",
            task_type=self._resolve_task_type(),
            sensitivity_level=self._resolve_sensitivity(),
            priority=self._resolve_priority(),
            redaction_policy=self._get_redaction_policy(),
        )

        if USE_GATEWAY and _gateway:
            response = await _gateway.route(request)
        else:
            if _redact_layer and _redact_layer.enabled:
                request = await _redact_layer.apply(request)
            response = await model_router.route(request, tier=tier)

        if session_id and conversation_manager:
            session = conversation_manager.get(session_id, self.config.role)
            if session:
                session.add_assistant_message(response.content or "")

        return response

    async def retrieve_context(
        self,
        query_summary: str,
        mission_id: str,
        tenant_id: str = "default",
    ) -> str:
        """Retrieve relevant past decisions via pre-turn RAG (ADR-018 §3.2).

        Skips RAG on turn 1 (no history to retrieve). Truncates results
        to the tier token budget.

        Args:
            query_summary: Brief description of the current alert/task.
            mission_id: Current mission ID.
            tenant_id: Tenant identifier for isolation.

        Returns:
            Context string with relevant past decisions, or empty string.
        """
        # Skip RAG on first turn (no relevant history yet)
        if self.turn_count <= 1:
            return ""

        try:
            from magenta.mesh.memory import memory_mcp

            result = await memory_mcp.search_episodes(
                query=query_summary,
                agent_role=self.config.role,
                mission_id=mission_id,
                tenant_id=tenant_id,
                top_k=5,
            )

            if result.get("status") != "success":
                return ""

            episodes = result.get("results", [])
            if not episodes:
                return ""

            # Build context from retrieved episodes
            context_parts = ["Relevant Past Decisions:"]
            for ep in episodes:
                text = ep.get("text", "")
                score = ep.get("score", 0)
                context_parts.append(f"- [{score:.2f}] {text}")

            context = "\n".join(context_parts)

            # Truncate to tier token budget
            budget = TIER_TOKEN_BUDGETS.get(self.task_type, 1000)
            estimated_tokens = len(context) // 4
            if estimated_tokens > budget:
                max_chars = budget * 4
                context = context[:max_chars] + "\n[truncated to budget]"

            return context

        except Exception:
            import logging

            logging.getLogger(__name__).exception("Failed to retrieve memory context")
            return ""

    async def log_activity(
        self,
        mission: Mission,
        action: str,
        status: ActionStatus,
        tenant_id: str = "default",
    ) -> None:
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
                    "tenant_id": tenant_id,
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
