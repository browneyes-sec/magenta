"""
Magenta Artifact Generator — HTML dashboard artifacts for Open WebUI (HTTP client).

Provides six artifact generators that produce interactive HTML cards
for display in Open WebUI chat.

Installation: place in Open WebUI pipelines directory, enable in Valves.
"""

import logging
from datetime import datetime

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
        if not parts:
            return self._help()

        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "generate_artifact" or cmd in ARTIFACT_TYPES:
            artifact_type = arg if cmd == "generate_artifact" else cmd
            import asyncio

            return asyncio.run(self._generate_artifact(artifact_type))

        return self._help()

    def _help(self) -> str:
        return f"""Magenta Artifact Generator

Available artifacts: {", ".join(ARTIFACT_TYPES)}

Usage:
```
generate_artifact <type>
# or just
<type>
```

Examples:
```
generate_artifact mission_throughput
threat_analytics
directive_timeline
```"""

    async def _generate_artifact(self, artifact_type: str) -> str:
        """Generate an HTML artifact."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.get(f"{API_BASE}/mcp/artifacts")
                r.raise_for_status()
                artifacts = r.json()
        except Exception as exc:
            logger.warning("Could not load artifact list: %s", exc)
            artifacts = {}

        if artifact_type not in ARTIFACT_TYPES:
            return f"Unknown artifact type: {artifact_type}. Available: {', '.join(ARTIFACT_TYPES)}"

        artifact = artifacts.get(artifact_type, {})
        desc = artifact.get("description", f"{artifact_type} dashboard")

        return self._render_artifact(artifact_type, desc)

    def _render_artifact(self, artifact_type: str, description: str) -> str:
        """Render artifact as HTML."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""<div style="font-family:system-ui,-apple-system,sans-serif;max-width:800px;margin:0 auto">
    <div style="background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1);padding:24px">
        <h2 style="margin:0 0 8px 0;font-size:20px;color:#333">{artifact_type.replace("_", " ").title()}</h2>
        <p style="margin:0 0 16px 0;font-size:14px;color:#666">{description}</p>
        <div style="background:#f8fafc;border-radius:8px;padding:16px;font-family:monospace;font-size:13px;color:#334155;white-space:pre-wrap;overflow-x:auto">
[{{ "type": "{artifact_type}", "description": "{description}", "generated": "{now}", "status": "mock" }}]
        </div>
        <div style="margin-top:16px;padding:12px;background:#f0fdf4;border-radius:8px;font-size:13px;color:#166534">
            This is a mock artifact. Connect to real data sources for production use.
        </div>
    </div>
</div>"""
