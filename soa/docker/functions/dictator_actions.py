"""
Dictator Actions — CLI action bridge for Open WebUI.

Provides a Python-based bridge between Open WebUI function calls
and the Magenta Dictator CLI/API.

All actions are idempotent and logged to the audit trail.
"""

import logging

logger = logging.getLogger(__name__)


class DictatorActions:
    """Bridge class between Open WebUI and Magenta Dictator."""

    @staticmethod
    async def get_status() -> dict:
        """Get full framework status."""
        from magenta.agents.dictator import dictator

        return await dictator.get_framework_status()

    @staticmethod
    async def get_oversight() -> dict:
        """Get the oversight board."""
        from magenta.agents.dictator import dictator

        return await dictator.get_oversight_board()

    @staticmethod
    async def issue_directive(
        dtype: str, target: str, mission_id: str = "", payload: dict = None, reason: str = ""
    ) -> dict:
        """Issue a directive via the Dictator."""
        from magenta.dictator.directives import DirectiveType
        from magenta.dictator.directives import issue_directive as issue

        try:
            directive_type = DirectiveType(dtype)
        except ValueError:
            return {"status": "error", "error": f"Invalid directive type: {dtype}"}

        directive = issue(
            dtype=directive_type,
            target=target,
            mission_id=mission_id or None,
            payload=payload or {},
            reason=reason,
        )
        return {"status": "issued", "directive_id": directive.directive_id}

    @staticmethod
    async def halt_mission(mission_id: str, reason: str = "Operator request") -> dict:
        """Halt a running mission."""
        from magenta.agents.dictator import dictator

        return await dictator.halt_mission(mission_id, reason)

    @staticmethod
    async def escalate_mission(mission_id: str, reason: str = "") -> dict:
        """Escalate a mission."""
        from magenta.agents.dictator import dictator

        return await dictator.escalate_mission(mission_id, reason)

    @staticmethod
    async def deploy_agent(role: str, model: str | None = None) -> dict:
        """Deploy an agent by role."""
        from magenta.agents.dictator import dictator

        kwargs = {}
        if model:
            kwargs["model_name"] = model
        agent = await dictator.deploy_agent(role, **kwargs)
        return {"status": "deployed", "agent_id": agent.agent_id, "role": agent.role}

    @staticmethod
    async def recall_agent(agent_id: str) -> dict:
        """Recall an agent."""
        from magenta.agents.dictator import dictator

        result = await dictator.recall_agent(agent_id)
        if not result:
            return {"status": "error", "error": f"Agent {agent_id} not found"}
        return {"status": "recalled", "agent_id": agent_id}

    @staticmethod
    async def override_teaming(mission_id: str, structure: str) -> dict:
        """Override teaming structure."""
        from magenta.agents.dictator import dictator

        valid = ["pipeline", "supervisor", "debate", "mesh", "referee"]
        if structure not in valid:
            return {"status": "error", "error": f"Invalid structure: {structure}. Valid: {valid}"}
        return await dictator.override_teaming(mission_id, structure)

    @staticmethod
    async def apply_policy_override(name: str, teaming: str, priority: str = "normal") -> dict:
        """Apply a policy override."""
        from magenta.agents.dictator import dictator
        from magenta.dictator.policies import OrchestrationPolicy

        policy = OrchestrationPolicy(name=name, teaming_structure=teaming, priority=priority)
        return await dictator.apply_policy_override(policy)

    @staticmethod
    async def clear_policy_overrides() -> dict:
        """Clear all policy overrides."""
        from magenta.agents.dictator import dictator

        return await dictator.clear_policy_overrides()

    @staticmethod
    async def get_pending_approvals() -> list[dict]:
        """Get list of pending approvals."""
        from magenta.response.executor import approval_gate

        return await approval_gate.list_pending()

    @staticmethod
    async def approve_action(approval_id: str) -> dict:
        """Approve a pending action."""
        from magenta.response.executor import approval_gate

        try:
            return await approval_gate.approve(approval_id, "operator")
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @staticmethod
    async def deny_action(approval_id: str, reason: str = "") -> dict:
        """Deny a pending action."""
        from magenta.response.executor import approval_gate

        try:
            return await approval_gate.reject(approval_id, reason)
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @staticmethod
    async def run_probes() -> dict:
        """Run magnet probes and return results."""
        import asyncio
        import importlib

        results = {}
        for name in ["dictator_probe"]:
            try:
                mod = importlib.import_module(f"magnet.probes.{name}")
                if asyncio.iscoroutinefunction(mod.run):
                    results[name] = await mod.run()
                else:
                    results[name] = mod.run()
            except Exception as exc:
                results[name] = {"status": "error", "error": str(exc)}
        return {"probes": results}


dictator_actions = DictatorActions()
