"""
Magenta Artifact Generator — HTML dashboard artifacts for Open WebUI.

Provides six artifact generators that produce interactive HTML cards
for display in Open WebUI chat.

Installation: place in Open WebUI pipelines directory, enable in Valves.
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

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
        self.type = "pipe"
        self.name = "Magenta Artifact Generator"
        self.pipeline = "magenta_artifact_generator"

    async def on_startup(self) -> None:
        logger.info("Magenta Artifact Generator pipeline started")

    async def on_shutdown(self) -> None:
        logger.info("Magenta Artifact Generator pipeline stopped")

    async def pipe(self, body: dict) -> str:
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
        from magenta.dictator.state import dictator_state
        active = len(dictator_state.active_missions)
        completed = len(dictator_state.completed_missions)
        directives = len(dictator_state.directive_log)

        return f"""<div style="font-family:system-ui,sans-serif;max-width:100%">
    <div style="background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,0.1);padding:20px">
        <h3 style="margin:0 0 16px 0;font-size:16px">Mission Throughput</h3>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
            <div style="background:#e3f2fd;padding:16px;border-radius:8px;text-align:center">
                <div style="font-size:32px;font-weight:700;color:#1565c0">{active}</div>
                <div style="font-size:12px;color:#666;margin-top:4px">Active Missions</div>
            </div>
            <div style="background:#e8f5e9;padding:16px;border-radius:8px;text-align:center">
                <div style="font-size:32px;font-weight:700;color:#2e7d32">{completed}</div>
                <div style="font-size:12px;color:#666;margin-top:4px">Completed</div>
            </div>
            <div style="background:#fff3e0;padding:16px;border-radius:8px;text-align:center">
                <div style="font-size:32px;font-weight:700;color:#e65100">{directives}</div>
                <div style="font-size:12px;color:#666;margin-top:4px">Directives Issued</div>
            </div>
        </div>
        <div style="margin-top:12px;font-size:12px;color:#999;text-align:center">
            Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
        </div>
    </div>
</div>"""

    async def _threat_analytics(self) -> str:
        return """<div style="font-family:system-ui,sans-serif;max-width:100%">
    <div style="background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,0.1);padding:20px">
        <h3 style="margin:0 0 12px 0;font-size:16px">Threat Analytics</h3>
        <p style="font-size:13px;color:#666;margin:0 0 12px 0">Integrated alert sources: Sentinel, Defender</p>
        <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px">
            <div style="background:#fef2f2;padding:12px;border-radius:6px;font-size:13px">
                <span style="color:#991b1b;font-weight:600">Critical:</span> 0
            </div>
            <div style="background:#fff7ed;padding:12px;border-radius:6px;font-size:13px">
                <span style="color:#c2410c;font-weight:600">High:</span> 0
            </div>
            <div style="background:#fefce8;padding:12px;border-radius:6px;font-size:13px">
                <span style="color:#a16207;font-weight:600">Medium:</span> 0
            </div>
            <div style="background:#f0fdf4;padding:12px;border-radius:6px;font-size:13px">
                <span style="color:#166534;font-weight:600">Low:</span> 0
            </div>
        </div>
        <p style="font-size:12px;color:#999;margin:12px 0 0 0">Connectors not configured. Alerts will appear once connected.</p>
    </div>
</div>"""

    async def _blue_team_ops(self) -> str:
        return """<div style="font-family:system-ui,sans-serif;max-width:100%">
    <div style="background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,0.1);padding:20px">
        <h3 style="margin:0 0 12px 0;font-size:16px">Blue Team Ops</h3>
        <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:12px">
            <div style="background:#f3e8ff;padding:12px;border-radius:6px;text-align:center">
                <div style="font-size:24px;font-weight:700;color:#7c3aed">0</div>
                <div style="font-size:12px;color:#666">Hosts Isolated</div>
            </div>
            <div style="background:#e0f2fe;padding:12px;border-radius:6px;text-align:center">
                <div style="font-size:24px;font-weight:700;color:#0369a1">0</div>
                <div style="font-size:12px;color:#666">Accounts Disabled</div>
            </div>
        </div>
        <div style="background:#f9fafb;border-radius:6px;padding:12px">
            <div style="font-size:13px;font-weight:600;margin-bottom:8px">Recent Actions</div>
            <div style="font-size:12px;color:#999">No actions taken yet. Actions will appear here as they execute.</div>
        </div>
    </div>
</div>"""

    async def _directive_timeline(self) -> str:
        from magenta.dictator.state import dictator_state
        directives = dictator_state.directive_log[-20:]
        rows = ""
        for d in directives:
            rows += f"""<tr>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("type", "")}</td>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("target", "")}</td>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("reason", "")[:48]}</td>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("priority", "")}</td>
            </tr>"""
        return f"""<div style="font-family:system-ui,sans-serif;max-width:100%">
    <div style="background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,0.1);padding:20px">
        <h3 style="margin:0 0 12px 0;font-size:16px">Directive Timeline</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead><tr style="background:#f5f5f5">
                <th style="padding:8px;text-align:left;font-size:11px;color:#666;text-transform:uppercase">Type</th>
                <th style="padding:8px;text-align:left;font-size:11px;color:#666;text-transform:uppercase">Target</th>
                <th style="padding:8px;text-align:left;font-size:11px;color:#666;text-transform:uppercase">Reason</th>
                <th style="padding:8px;text-align:left;font-size:11px;color:#666;text-transform:uppercase">Priority</th>
            </tr></thead>
            <tbody>{rows if rows else '<tr><td colspan="4" style="padding:16px;text-align:center;color:#999">No directives issued yet</td></tr>'}</tbody>
        </table>
    </div>
</div>"""

    async def _policy_status(self) -> str:
        from magenta.dictator.policies import policy_engine
        policies = [p.model_dump() for p in policy_engine._policies]
        overrides = {n: p.model_dump() for n, p in policy_engine._overrides.items()}
        rows = ""
        for p in policies:
            icon = "\u2705" if p.get("enabled", True) else "\u274c"
            rows += f"""<tr>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:13px">{icon}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:13px">{p.get("name", "")}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:13px">{p.get("teaming_structure", "")}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:13px">{p.get("priority", "normal")}</td>
            </tr>"""
        overrides_text = ", ".join(overrides.keys()) if overrides else "None active"
        return f"""<div style="font-family:system-ui,sans-serif;max-width:100%">
    <div style="background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,0.1);padding:20px">
        <h3 style="margin:0 0 4px 0;font-size:16px">Policy Status</h3>
        <p style="font-size:12px;color:#666;margin:0 0 12px 0">Overrides: {overrides_text}</p>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead><tr style="background:#f5f5f5">
                <th style="padding:8px;text-align:left;font-size:11px;color:#666;text-transform:uppercase">Active</th>
                <th style="padding:8px;text-align:left;font-size:11px;color:#666;text-transform:uppercase">Policy</th>
                <th style="padding:8px;text-align:left;font-size:11px;color:#666;text-transform:uppercase">Teaming</th>
                <th style="padding:8px;text-align:left;font-size:11px;color:#666;text-transform:uppercase">Priority</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
</div>"""

    async def _dead_letter(self) -> str:
        from magenta.dictator.state import dictator_state
        failed = [d for d in dictator_state.directive_log if d.get("executed") is False]
        rows = ""
        for d in failed[-20:]:
            rows += f"""<tr>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("type", "")}</td>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("target", "")}</td>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("reason", "")[:40]}</td>
            </tr>"""
        return f"""<div style="font-family:system-ui,sans-serif;max-width:100%">
    <div style="background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,0.1);padding:20px">
        <h3 style="margin:0 0 4px 0;font-size:16px">Dead Letter Queue</h3>
        <p style="font-size:12px;color:#666;margin:0 0 12px 0">{len(failed)} failed directives</p>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead><tr style="background:#f5f5f5">
                <th style="padding:8px;text-align:left;font-size:11px;color:#666;text-transform:uppercase">Type</th>
                <th style="padding:8px;text-align:left;font-size:11px;color:#666;text-transform:uppercase">Target</th>
                <th style="padding:8px;text-align:left;font-size:11px;color:#666;text-transform:uppercase">Reason</th>
            </tr></thead>
            <tbody>{rows if rows else '<tr><td colspan="3" style="padding:16px;text-align:center;color:#999">No dead letters</td></tr>'}</tbody>
        </table>
    </div>
</div>"""
