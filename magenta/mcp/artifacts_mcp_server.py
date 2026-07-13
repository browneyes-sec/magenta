"""MCP server — Artifact generation for Open WebUI dashboards."""


class ArtifactsMCPServer:
    """MCP tools for generating Open WebUI artifacts."""

    def __init__(self):
        self.name = "artifacts"
        self.description = "Artifact generation MCP tools"

    async def generate_directive_timeline(self, limit: int = 20) -> dict:
        """Generate an HTML directive timeline artifact.

        Args:
            limit: Number of recent directives to include.

        Returns:
            HTML artifact string.
        """
        from magenta.dictator.state import dictator_state
        from magenta.dictator.telemetry import generate_directive_timeline_artifact

        directives = dictator_state.directive_log[-limit:]
        html = generate_directive_timeline_artifact(directives)
        return {"status": "success", "artifact_type": "directive_timeline", "html": html}

    async def generate_mission_throughput(self) -> dict:
        """Generate a mission throughput summary artifact.

        Returns:
            HTML artifact with mission stats.
        """
        from magenta.dictator.state import dictator_state

        active = len(dictator_state.active_missions)
        completed = len(dictator_state.completed_missions)
        total_directives = len(dictator_state.directive_log)

        html = f"""<div style="font-family:system-ui,sans-serif;max-width:100%">
        <h3 style="margin:0 0 12px 0;font-size:16px">Mission Throughput</h3>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
            <div style="background:#e3f2fd;padding:16px;border-radius:8px;text-align:center">
                <div style="font-size:28px;font-weight:700;color:#1565c0">{active}</div>
                <div style="font-size:12px;color:#666;margin-top:4px">Active Missions</div>
            </div>
            <div style="background:#e8f5e9;padding:16px;border-radius:8px;text-align:center">
                <div style="font-size:28px;font-weight:700;color:#2e7d32">{completed}</div>
                <div style="font-size:12px;color:#666;margin-top:4px">Completed Missions</div>
            </div>
            <div style="background:#fff3e0;padding:16px;border-radius:8px;text-align:center">
                <div style="font-size:28px;font-weight:700;color:#e65100">{total_directives}</div>
                <div style="font-size:12px;color:#666;margin-top:4px">Total Directives</div>
            </div>
        </div></div>"""
        return {"status": "success", "artifact_type": "mission_throughput", "html": html}

    async def generate_policy_status(self) -> dict:
        """Generate a policy status artifact.

        Returns:
            HTML artifact with active policies and overrides.
        """
        from magenta.dictator.policies import policy_engine

        policies = [p.model_dump() for p in policy_engine._policies]
        overrides = {n: p.model_dump() for n, p in policy_engine._overrides.items()}

        rows = []
        for p in policies:
            status_icon = "\u2705" if p.get("enabled", True) else "\u274c"
            rows.append(f"""<tr>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:13px">{status_icon}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:13px">{p.get("name", "")}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:13px">{p.get("teaming_structure", "")}</td>
                <td style="padding:6px 10px;border-bottom:1px solid #eee;font-size:13px">{p.get("priority", "normal")}</td>
            </tr>""")

        override_text = ", ".join(overrides.keys()) if overrides else "None"
        html = f"""<div style="font-family:system-ui,sans-serif;max-width:100%">
        <h3 style="margin:0 0 8px 0;font-size:16px">Policy Status</h3>
        <p style="font-size:13px;color:#666;margin:0 0 8px 0">Active Overrides: {override_text}</p>
        <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
            <thead><tr style="background:#f5f5f5">
                <th style="padding:8px;text-align:left;font-size:12px;color:#666;text-transform:uppercase">Active</th>
                <th style="padding:8px;text-align:left;font-size:12px;color:#666;text-transform:uppercase">Policy</th>
                <th style="padding:8px;text-align:left;font-size:12px;color:#666;text-transform:uppercase">Teaming</th>
                <th style="padding:8px;text-align:left;font-size:12px;color:#666;text-transform:uppercase">Priority</th>
            </tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table></div>"""
        return {"status": "success", "artifact_type": "policy_status", "html": html}

    async def generate_dead_letter(self) -> dict:
        """Generate a dead-letter queue artifact.

        Returns:
            HTML artifact with failed or rejected items.
        """
        from magenta.dictator.state import dictator_state

        failed = [d for d in dictator_state.directive_log if d.get("executed") is False]

        rows = []
        for d in failed[-20:]:
            rows.append(f"""<tr>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("type", "")}</td>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("target", "")}</td>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:13px">{d.get("reason", "")[:40]}</td>
            </tr>""")

        html = f"""<div style="font-family:system-ui,sans-serif;max-width:100%">
        <h3 style="margin:0 0 8px 0;font-size:16px">Dead Letter Queue</h3>
        <p style="font-size:13px;color:#666;margin:0 0 8px 0">{len(failed)} failed directives</p>
        <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
            <thead><tr style="background:#f5f5f5">
                <th style="padding:8px;text-align:left;font-size:12px;color:#666;text-transform:uppercase">Type</th>
                <th style="padding:8px;text-align:left;font-size:12px;color:#666;text-transform:uppercase">Target</th>
                <th style="padding:8px;text-align:left;font-size:12px;color:#666;text-transform:uppercase">Reason</th>
            </tr></thead>
            <tbody>{"".join(rows) if rows else '<tr><td colspan="3" style="padding:16px;text-align:center;color:#999;font-size:13px">No dead letters</td></tr>'}</tbody>
        </table></div>"""
        return {"status": "success", "artifact_type": "dead_letter", "html": html}

    async def get_tools(self) -> list[dict]:
        """Return MCP tool definitions for this server."""
        return [
            {
                "name": "generate_directive_timeline",
                "description": "Generate an HTML directive timeline artifact",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20},
                    },
                },
            },
            {
                "name": "generate_mission_throughput",
                "description": "Generate a mission throughput summary artifact",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "generate_policy_status",
                "description": "Generate a policy status artifact",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "generate_dead_letter",
                "description": "Generate a dead-letter queue artifact",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]


artifacts_mcp = ArtifactsMCPServer()
