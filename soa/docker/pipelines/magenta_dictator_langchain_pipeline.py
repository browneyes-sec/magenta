"""
Magenta Dictator Pipeline — Open WebUI / LangChain pipe.

Provides 15+ tools for issuing Dictator directives, checking approval
queue, managing policies, generating artifacts, and querying framework
state.

Installation: place in Open WebUI pipelines directory, enable in Valves.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Pipeline:
    """Open WebUI Pipeline for Magenta Dictator operations."""

    def __init__(self):
        self.type = "pipe"
        self.name = "Magenta Dictator Pipeline"
        self.pipeline = "magenta_dictator_pipe"

    async def on_startup(self) -> None:
        logger.info("Magenta Dictator Pipeline started")

    async def on_shutdown(self) -> None:
        logger.info("Magenta Dictator Pipeline stopped")

    async def pipe(self, body: dict) -> str:
        """Route incoming request to the appropriate tool."""
        messages = body.get("messages", [])
        if not messages:
            return "No messages provided"

        last = messages[-1]
        content = last.get("content", "") if isinstance(last, dict) else str(last)

        return await self._route_tool(content)

    async def _route_tool(self, content: str) -> str:
        """Parse and route tool calls from the user message."""
        tools = {
            "check_pending_approvals": self._check_pending_approvals,
            "policy_list": self._policy_list,
            "policy_set": self._policy_set,
            "policy_clear": self._policy_clear,
            "dictator_status": self._dictator_status,
            "dictator_halt": self._dictator_halt,
            "dictator_deploy": self._dictator_deploy,
            "dictator_escalate": self._dictator_escalate,
            "dictator_override_teaming": self._dictator_override_teaming,
            "connector_health": self._connector_health,
            "registry_search": self._registry_search,
            "save_artifact": self._save_artifact,
            "generate_artifact": self._generate_artifact,
        }

        for prefix, handler in tools.items():
            if content.strip().startswith(prefix):
                args = content[len(prefix):].strip()
                return await handler(args)

        return (
            "Available commands:\n"
            "- check_pending_approvals\n"
            "- policy_list\n"
            "- policy_set <name> <teaming> <priority>\n"
            "- policy_clear\n"
            "- dictator_status\n"
            "- dictator_halt <mission_id> [reason]\n"
            "- dictator_deploy <role> [model]\n"
            "- dictator_escalate <mission_id> [reason]\n"
            "- dictator_override_teaming <mission_id> <structure>\n"
            "- connector_health\n"
            "- registry_search [query]\n"
            "- save_artifact <path> <content>\n"
            "- generate_artifact <type>\n"
        )

    async def _check_pending_approvals(self, _args: str) -> str:
        try:
            from magenta.response.executor import approval_gate
            pending = await approval_gate.list_pending()
            if not pending:
                return "No pending approvals."
            lines = [f"- **{a['id']}**: {a['action']} on {a['target']} (risk: {a['risk_score']})" for a in pending]
            return f"### Pending Approvals ({len(pending)})\n" + "\n".join(lines)
        except Exception as exc:
            return f"Error: {exc}"

    async def _policy_list(self, _args: str) -> str:
        try:
            from magenta.dictator.policies import policy_engine
            policies = [p.model_dump() for p in policy_engine._policies]
            overrides = {n: p.model_dump() for n, p in policy_engine._overrides.items()}
            lines = [f"- **{p.get('name')}** ({p.get('teaming_structure')}) - {'enabled' if p.get('enabled') else 'disabled'}" for p in policies]
            result = "### Policies\n" + "\n".join(lines)
            if overrides:
                result += "\n\n### Active Overrides\n" + "\n".join(f"- **{k}**: {v}" for k, v in overrides.items())
            return result
        except Exception as exc:
            return f"Error: {exc}"

    async def _policy_set(self, args: str) -> str:
        parts = args.split()
        if len(parts) < 3:
            return "Usage: policy_set <name> <teaming> <priority>"
        name, teaming, priority = parts[0], parts[1], parts[2]
        try:
            from magenta.dictator.policies import OrchestrationPolicy
            policy = OrchestrationPolicy(name=name, teaming_structure=teaming, priority=priority)
            from magenta.agents.dictator import dictator
            await dictator.apply_policy_override(policy)
            return f"Policy override set: {name} ({teaming}, {priority})"
        except Exception as exc:
            return f"Error: {exc}"

    async def _policy_clear(self, _args: str) -> str:
        try:
            from magenta.agents.dictator import dictator
            await dictator.clear_policy_overrides()
            return "All policy overrides cleared."
        except Exception as exc:
            return f"Error: {exc}"

    async def _dictator_status(self, _args: str) -> str:
        try:
            from magenta.agents.dictator import dictator
            status = await dictator.get_framework_status()
            return json.dumps(status, indent=2, default=str)
        except Exception as exc:
            return f"Error: {exc}"

    async def _dictator_halt(self, args: str) -> str:
        parts = args.split(maxsplit=1)
        if not parts:
            return "Usage: dictator_halt <mission_id> [reason]"
        mission_id = parts[0]
        reason = parts[1] if len(parts) > 1 else "Operator request via pipeline"
        try:
            from magenta.agents.dictator import dictator
            result = await dictator.halt_mission(mission_id, reason)
            return json.dumps(result, indent=2, default=str)
        except Exception as exc:
            return f"Error: {exc}"

    async def _dictator_deploy(self, args: str) -> str:
        parts = args.split()
        if not parts:
            return "Usage: dictator_deploy <role> [model]"
        role = parts[0]
        model = parts[1] if len(parts) > 1 else None
        try:
            from magenta.agents.dictator import dictator
            kwargs = {}
            if model:
                kwargs["model_name"] = model
            agent = await dictator.deploy_agent(role, **kwargs)
            return f"Agent deployed: {agent.agent_id} ({agent.role}) on {agent.config.model_provider}/{agent.config.model_name}"
        except Exception as exc:
            return f"Error: {exc}"

    async def _dictator_escalate(self, args: str) -> str:
        parts = args.split(maxsplit=1)
        if not parts:
            return "Usage: dictator_escalate <mission_id> [reason]"
        mission_id = parts[0]
        reason = parts[1] if len(parts) > 1 else ""
        try:
            from magenta.agents.dictator import dictator
            result = await dictator.escalate_mission(mission_id, reason)
            return json.dumps(result, indent=2, default=str)
        except Exception as exc:
            return f"Error: {exc}"

    async def _dictator_override_teaming(self, args: str) -> str:
        parts = args.split()
        if len(parts) < 2:
            return "Usage: dictator_override_teaming <mission_id> <structure>"
        mission_id, structure = parts[0], parts[1]
        valid = ["pipeline", "supervisor", "debate", "mesh", "referee"]
        if structure not in valid:
            return f"Invalid structure. Must be one of: {', '.join(valid)}"
        try:
            from magenta.agents.dictator import dictator
            result = await dictator.override_teaming(mission_id, structure)
            return json.dumps(result, indent=2, default=str)
        except Exception as exc:
            return f"Error: {exc}"

    async def _connector_health(self, _args: str) -> str:
        try:
            from magenta.integration.sentinel import sentinel_connector
            from magenta.integration.entra import entra_connector
            from magenta.integration.defender import defender_connector
            # These will return degraded status since connectors are not configured
            sentinel = await sentinel_connector.health_check() if hasattr(sentinel_connector, 'health_check') else {"sentinel": "not_configured"}
            entra = await entra_connector.health_check() if hasattr(entra_connector, 'health_check') else {"entra": "not_configured"}
            defender = await defender_connector.health_check() if hasattr(defender_connector, 'health_check') else {"defender": "not_configured"}
            return json.dumps({"sentinel": sentinel, "entra": entra, "defender": defender}, indent=2)
        except Exception as exc:
            return f"Error: {exc}"

    async def _registry_search(self, args: str) -> str:
        query = args.strip() or ""
        try:
            from magenta.data.sql.mission_repo import mission_repository
            missions = await mission_repository.search(query=query)
            if not missions:
                return "No missions found."
            lines = [f"- **{m.mission_id}**: {m.status} ({m.severity})" for m in missions[:10]]
            return "### Missions\n" + "\n".join(lines)
        except Exception as exc:
            return f"Error: {exc}"

    async def _save_artifact(self, args: str) -> str:
        import ast
        try:
            parsed = ast.literal_eval(args)
            path = parsed.get("path", "")
            content = parsed.get("content", "")
            if not path or not content:
                return "Usage: save_artifact {'path': '<path>', 'content': '<content>'}"
            from magenta.mcp.datalake_mcp_server import datalake_mcp
            result = await datalake_mcp.save_artifact(path, content)
            return json.dumps(result, indent=2)
        except Exception as exc:
            return f"Error: {exc}"

    async def _generate_artifact(self, args: str) -> str:
        atype = args.strip()
        try:
            from magenta.mcp.artifacts_mcp_server import artifacts_mcp
            generators = {
                "trend": artifacts_mcp.generate_mission_throughput,
                "directive_timeline": artifacts_mcp.generate_directive_timeline,
                "policy_status": artifacts_mcp.generate_policy_status,
                "dead_letter": artifacts_mcp.generate_dead_letter,
            }
            if atype == "list":
                return f"Available artifact types: {', '.join(generators.keys())}"
            handler = generators.get(atype)
            if not handler:
                return f"Unknown artifact type: {atype}. Available: {', '.join(generators.keys())}"
            result = await handler()
            return result.get("html", json.dumps(result))
        except Exception as exc:
            return f"Error: {exc}"
