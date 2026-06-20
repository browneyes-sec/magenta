"""
Magenta Artifact Generator — HTML dashboard artifacts for Open WebUI (HTTP client).

Provides six artifact generators that produce interactive HTML cards
for display in Open WebUI chat.

Installation: place in Open WebUI pipelines directory, enable in Valves.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

API_BASE = "http://magenta-api:8000"
TIMEOUT = 30.0


class Valves(BaseModel):
    enabled: bool = True
    priority: int = 8
    name: str = "Magenta Artifact Generator"
    description: str = "Generate HTML dashboard artifacts for mission state, threats, and policies"
    pipelines: list = []


ARTIFACT_TYPES = [
    "mission_throughput",
    "threat_analytics",
    "blue_team_ops",
    "directive_timeline",
    "policy_status",
    "dead_letter",
]


class Pipeline:
    """Artifact Generator pipeline — produces HTML dashboard artifacts."""

    def __init__(self):
        self.id = "magenta_artifact_generator"
        self.name = "Magenta Artifact Generator"
        self.pipeline = "magenta_artifact_generator"
        self.valves = Valves()

    async def on_startup(self) -> None:
        logger.info("Magenta Artifact Generator pipeline started")

    async def on_shutdown(self) -> None:
        logger.info("Magenta Artifact Generator pipeline stopped")

    def pipe(self, body: dict, **kwargs) -> str:
        messages = body.get("messages", [])
        last_content = ""
        if messages:
            last = messages[-1]
            last_content = last.get("content", "") if isinstance(last, dict) else str(last)

        parts = last_content.strip().split(maxsplit=1)
        if len(parts) == 2 and parts[0] == "generate_artifact":
            atype = parts[1].strip()
            return await self._generate(atype)

        type_list = ", ".join(ARTIFACT_TYPES)
        return f"""Generate an artifact with: `generate_artifact <type>`

Available types: {type_list}

Example:
```
generate_artifact mission_throughput
```"""

    async def _get(self, path: str):
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{API_BASE}{path}")
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, json_data: dict = None):
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(f"{API_BASE}{path}", json=json_data)
            r.raise_for_status()
            return r.json()

    async def _generate(self, atype: str) -> str:
        generators = {
            "mission_throughput": self._mission_throughput,
            "threat_analytics": self._threat_analytics,
            "blue_team_ops": self._blue_team_ops,
            "directive_timeline": self._directive_timeline,
            "policy_status": self._policy_status,
            "dead_letter": self._dead_letter,
        }

        handler = generators.get(atype)
        if not handler:
            return f"Unknown artifact type: {atype}. Available: {', '.join(ARTIFACT_TYPES)}"

        return await handler()

    async def _mission_throughput(self) -> str:
        try:
            data = await self._get("/mcp/artifacts")
            return data.get("mission_throughput", {}).get("html", "Error generating artifact")
        except Exception as exc:
            return f"Error: {exc}"

    async def _threat_analytics(self) -> str:
        try:
            data = await self._get("/mcp/artifacts")
            return data.get("threat_analytics", {}).get("html", "Error generating artifact")
        except Exception as exc:
            return f"Error: {exc}"

    async def _blue_team_ops(self) -> str:
        try:
            data = await self._get("/mcp/artifacts")
            return data.get("blue_team_ops", {}).get("html", "Error generating artifact")
        except Exception as exc:
            return f"Error: {exc}"

    async def _directive_timeline(self) -> str:
        try:
            data = await self._get("/mcp/artifacts")
            return data.get("directive_timeline", {}).get("html", "Error generating artifact")
        except Exception as exc:
            return f"Error: {exc}"

    async def _policy_status(self) -> str:
        try:
            data = await self._get("/mcp/artifacts")
            return data.get("policy_status", {}).get("html", "Error generating artifact")
        except Exception as exc:
            return f"Error: {exc}"

    async def _dead_letter(self) -> str:
        try:
            data = await self._get("/mcp/artifacts")
            return data.get("dead_letter", {}).get("html", "Error generating artifact")
        except Exception as exc:
            return f"Error: {exc}"