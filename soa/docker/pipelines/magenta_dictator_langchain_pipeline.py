"""
Magenta Dictator Pipeline — Open WebUI / LangChain pipe (HTTP client).

Provides 19 tools for issuing Dictator directives, checking approval
queue, managing policies, generating artifacts, querying framework
state, and operating agent memory via HTTP calls to magenta-api:8000.

Installation: place in Open WebUI pipelines directory, enable in Valves.
"""

import json
import logging
import os
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

API_BASE = "http://magenta-api:8000"
API_KEY = os.environ.get("OPENAI_API_KEY", "sk-magenta-pipeline")
TIMEOUT = 30.0


class Valves(BaseModel):
    enabled: bool = True
    priority: int = 10
    name: str = "Magenta Dictator Pipeline"
    description: str = "Issue Dictator directives, query status, manage agents, generate artifacts"
    pipelines: list = []


class Pipeline:
    """Open WebUI Pipeline for Magenta Dictator operations."""

    def __init__(self):
        self.id = "magenta_dictator_langchain_pipeline"
        self.name = "Magenta Dictator Pipeline"
        self.pipeline = "magenta_dictator_pipe"
        self.valves = Valves()

    async def on_startup(self) -> None:
        logger.info("Magenta Dictator Pipeline started")

    async def on_shutdown(self) -> None:
        logger.info("Magenta Dictator Pipeline stopped")

    def pipe(self, body: dict, **kwargs) -> str:
        """Route incoming request to the appropriate tool."""
        messages = body.get("messages", [])
        if not messages:
            return "No messages provided"

        last = messages[-1]
        content = last.get("content", "") if isinstance(last, dict) else str(last)

        import asyncio

        return asyncio.run(self._route_tool(content))

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
            "memory_write_episode": self._memory_write_episode,
            "memory_search_episodes": self._memory_search_episodes,
            "memory_write_semantic": self._memory_write_semantic,
            "memory_search_semantic": self._memory_search_semantic,
            "memory_write_procedure": self._memory_write_procedure,
            "memory_search_procedures": self._memory_search_procedures,
        }

        for prefix, handler in tools.items():
            if content.strip().startswith(prefix):
                args = content[len(prefix) :].strip()
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
            "- save_artifact {'path': '...', 'content': '...'}\n"
            "- generate_artifact <type>\n"
            "- memory_write_episode <agent_role> <mission_id> <turn> <text>\n"
            "- memory_search_episodes <query> [--role X] [--mission Y]\n"
            "- memory_write_semantic <text> [--product X] [--tags X,Y]\n"
            "- memory_search_semantic <query> [--product X] [--tags X,Y]\n"
            "- memory_write_procedure <tool_name> <text>\n"
            "- memory_search_procedures <query> [--tool X]"
        )

    async def _get(self, path: str) -> Any:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{API_BASE}{path}", headers={"X-API-Key": API_KEY})
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, json_data: dict = None, params: dict = None) -> Any:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                f"{API_BASE}{path}", json=json_data, params=params, headers={"X-API-Key": API_KEY}
            )
            r.raise_for_status()
            return r.json()

    async def _delete(self, path: str) -> Any:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.delete(f"{API_BASE}{path}", headers={"X-API-Key": API_KEY})
            r.raise_for_status()
            return r.json()

    async def _check_pending_approvals(self, _args: str) -> str:
        try:
            data = await self._get("/api/v1/approvals/pending")
            pending = data.get("approvals", []) if isinstance(data, dict) else data
            if not pending:
                return "No pending approvals."
            lines = [
                f"- **{a.get('id', 'N/A')}**: {a.get('action', 'N/A')} on {a.get('target', 'N/A')} (risk: {a.get('risk_score', 'N/A')})"
                for a in pending
            ]
            return f"### Pending Approvals ({len(pending)})\n" + "\n".join(lines)
        except Exception as exc:
            return f"Error: {exc}"

    async def _policy_list(self, _args: str) -> str:
        try:
            data = await self._get("/api/v1/dictator/policies")
            policies = data.get("policies", [])
            overrides = data.get("overrides", {})
            lines = [
                f"- **{p.get('name')}** ({p.get('teaming_structure')}) - {'enabled' if p.get('enabled') else 'disabled'}"
                for p in policies
            ]
            result = "### Policies\n" + "\n".join(lines)
            if overrides:
                result += "\n\n### Active Overrides\n" + "\n".join(
                    f"- **{k}**: {v}" for k, v in overrides.items()
                )
            return result
        except Exception as exc:
            return f"Error: {exc}"

    async def _policy_set(self, args: str) -> str:
        parts = args.split()
        if len(parts) < 3:
            return "Usage: policy_set <name> <teaming> <priority>"
        name, teaming, priority = parts[0], parts[1], parts[2]
        try:
            policy = {
                "name": name,
                "teaming_structure": teaming,
                "priority": priority,
                "enabled": True,
            }
            result = await self._post("/api/v1/dictator/policies/override", json_data=policy)  # noqa: F841
            return f"Policy override set: {name} ({teaming}, {priority})"
        except Exception as exc:
            return f"Error: {exc}"

    async def _policy_clear(self, _args: str) -> str:
        try:
            await self._delete("/api/v1/dictator/policies/overrides")
            return "All policy overrides cleared."
        except Exception as exc:
            return f"Error: {exc}"

    async def _dictator_status(self, _args: str) -> str:
        try:
            status = await self._get("/api/v1/dictator/status")
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
            result = await self._post(
                f"/api/v1/dictator/halt/{mission_id}", params={"reason": reason}
            )
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
            data = {}
            if model:
                data["model"] = model
            result = await self._post(f"/api/v1/dictator/deploy/{role}", json_data=data)
            return f"Agent deployed: {result.get('agent_id')} ({result.get('role')}) on {result.get('model')}"
        except Exception as exc:
            return f"Error: {exc}"

    async def _dictator_escalate(self, args: str) -> str:
        parts = args.split(maxsplit=1)
        if not parts:
            return "Usage: dictator_escalate <mission_id> [reason]"
        mission_id = parts[0]
        reason = parts[1] if len(parts) > 1 else ""
        try:
            result = await self._post(
                f"/api/v1/dictator/escalate/{mission_id}", params={"reason": reason}
            )
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
            result = await self._post(
                f"/api/v1/dictator/teaming/{mission_id}", json_data={"structure": structure}
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as exc:
            return f"Error: {exc}"

    async def _connector_health(self, _args: str) -> str:
        try:
            status = await self._get("/api/v1/dictator/status")
            connectors = status.get("connectors", {})
            return json.dumps(connectors, indent=2)
        except Exception as exc:
            return f"Error: {exc}"

    async def _registry_search(self, args: str) -> str:
        query = args.strip() or ""  # noqa: F841
        try:
            data = await self._get("/mcp/registry")
            missions = data.get("missions", [])
            if not missions:
                return "No missions found."
            lines = [
                f"- **{m.get('mission_id', '?')}**: {m.get('status', '?')} ({m.get('severity', '?')})"
                for m in missions[:10]
            ]
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
            result = await self._post(
                "/mcp/artifacts/save", json_data={"path": path, "content": content}
            )
            return json.dumps(result, indent=2)
        except Exception as exc:
            return f"Error: {exc}"

    async def _generate_artifact(self, args: str) -> str:
        atype = args.strip()
        try:
            data = await self._get("/mcp/artifacts")  # noqa: F841
            generators = {
                "trend": "mission_throughput",
                "directive_timeline": "directive_timeline",
                "policy_status": "policy_status",
                "dead_letter": "dead_letter",
            }
            if atype == "list":
                return f"Available artifact types: {', '.join(generators.keys())}"
            handler = generators.get(atype)
            if not handler:
                return f"Unknown artifact type: {atype}. Available: {', '.join(generators.keys())}"
            result = await self._post("/mcp/artifacts/generate", json_data={"type": handler})
            return result.get("html", json.dumps(result))
        except Exception as exc:
            return f"Error: {exc}"

    # ── Memory Tools (ADR-018) ──────────────────────────────────────

    def _parse_flags(self, args: str) -> tuple[str, dict[str, str]]:
        """Parse --key value flags from args string."""
        parts = args.split()
        positional = []
        flags = {}
        i = 0
        while i < len(parts):
            if parts[i].startswith("--") and i + 1 < len(parts):
                flags[parts[i][2:]] = parts[i + 1]
                i += 2
            else:
                positional.append(parts[i])
                i += 1
        return " ".join(positional), flags

    async def _memory_write_episode(self, args: str) -> str:
        """Write episodic memory: memory_write_episode <agent_role> <mission_id> <turn> <text>"""
        parts = args.split(maxsplit=3)
        if len(parts) < 4:
            return "Usage: memory_write_episode <agent_role> <mission_id> <turn> <text>"
        agent_role, mission_id, turn_str, text = parts
        try:
            turn_number = int(turn_str)
            result = await self._post(
                "/api/v1/mesh/memory/write-episode",
                json_data={
                    "agent_role": agent_role,
                    "mission_id": mission_id,
                    "turn_number": turn_number,
                    "text": text,
                    "correlation_id": "",
                    "metadata": {"source": "pipeline"},
                },
            )
            return f"Episode written: {result.get('chunks_ingested', 0)} chunks ingested"
        except Exception as exc:
            return f"Error: {exc}"

    async def _memory_search_episodes(self, args: str) -> str:
        """Search episodic memory: memory_search_episodes <query> [--role X] [--mission Y]"""
        query, flags = self._parse_flags(args)
        if not query:
            return "Usage: memory_search_episodes <query> [--role X] [--mission Y]"
        try:
            payload = {"query": query, "top_k": 5}
            if "role" in flags:
                payload["agent_role"] = flags["role"]
            if "mission" in flags:
                payload["mission_id"] = flags["mission"]
            results = await self._post("/api/v1/mesh/memory/search-episodic", json_data=payload)
            episodes = results.get("results", [])
            if not episodes:
                return "No matching episodes found."
            lines = [f"- [{e.get('score', 0):.2f}] {e.get('text', '')[:100]}" for e in episodes[:5]]
            return f"### Episodic Memory ({len(episodes)} results)\n" + "\n".join(lines)
        except Exception as exc:
            return f"Error: {exc}"

    async def _memory_write_semantic(self, args: str) -> str:
        """Write semantic memory: memory_write_semantic <text> [--product X] [--tags X,Y]"""
        text, flags = self._parse_flags(args)
        if not text:
            return "Usage: memory_write_semantic <text> [--product X] [--tags X,Y]"
        try:
            payload = {
                "text": text,
                "product": flags.get("product", ""),
                "tags": flags.get("tags", "").split(",") if flags.get("tags") else [],
                "metadata": {"source": "pipeline"},
            }
            result = await self._post("/api/v1/mesh/memory/write-semantic", json_data=payload)
            return f"Semantic memory written: {result.get('chunks_ingested', 0)} chunks"
        except Exception as exc:
            return f"Error: {exc}"

    async def _memory_search_semantic(self, args: str) -> str:
        """Search semantic memory: memory_search_semantic <query> [--product X] [--tags X,Y]"""
        query, flags = self._parse_flags(args)
        if not query:
            return "Usage: memory_search_semantic <query> [--product X] [--tags X,Y]"
        try:
            payload = {"query": query, "top_k": 5}
            if "product" in flags:
                payload["product"] = flags["product"]
            if "tags" in flags:
                payload["tags"] = flags["tags"].split(",")
            results = await self._post("/api/v1/mesh/memory/search-semantic", json_data=payload)
            items = results.get("results", [])
            if not items:
                return "No matching semantic memories found."
            lines = [f"- [{i.get('score', 0):.2f}] {i.get('text', '')[:100]}" for i in items[:5]]
            return f"### Semantic Memory ({len(items)} results)\n" + "\n".join(lines)
        except Exception as exc:
            return f"Error: {exc}"

    async def _memory_write_procedure(self, args: str) -> str:
        """Write procedural memory: memory_write_procedure <tool_name> <text>"""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: memory_write_procedure <tool_name> <text>"
        tool_name, text = parts
        try:
            result = await self._post(
                "/api/v1/mesh/memory/write-procedure",
                json_data={
                    "tool_name": tool_name,
                    "text": text,
                    "parameters": {},
                    "mission_id": "",
                    "metadata": {"source": "pipeline"},
                },
            )
            return f"Procedure written: {result.get('chunks_ingested', 0)} chunks"
        except Exception as exc:
            return f"Error: {exc}"

    async def _memory_search_procedures(self, args: str) -> str:
        """Search procedural memory: memory_search_procedures <query> [--tool X]"""
        query, flags = self._parse_flags(args)
        if not query:
            return "Usage: memory_search_procedures <query> [--tool X]"
        try:
            payload = {"query": query, "top_k": 5}
            if "tool" in flags:
                payload["tool_name"] = flags["tool"]
            results = await self._post("/api/v1/mesh/memory/search-procedures", json_data=payload)
            items = results.get("results", [])
            if not items:
                return "No matching procedures found."
            lines = [f"- [{i.get('score', 0):.2f}] {i.get('text', '')[:100]}" for i in items[:5]]
            return f"### Procedural Memory ({len(items)} results)\n" + "\n".join(lines)
        except Exception as exc:
            return f"Error: {exc}"
