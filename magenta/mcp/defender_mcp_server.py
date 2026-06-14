"""MCP server — Microsoft Defender for Endpoint machine status and alerts."""

from typing import Optional


class DefenderMCPServer:
    """MCP tools for Microsoft Defender for Endpoint."""

    def __init__(self):
        self.name = "defender"
        self.description = "Microsoft Defender for Endpoint MCP tools"

    async def get_machine(self, machine_id: str) -> dict:
        """Get Defender machine details.

        Args:
            machine_id: The machine's device ID.

        Returns:
            Machine details.
        """
        try:
            from magenta.integration.defender import defender_connector
            result = await defender_connector.get_machine(machine_id)
            return {"status": "success", "machine": result}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def list_machine_alerts(self, machine_id: str, limit: int = 20) -> dict:
        """List alerts for a specific Defender machine.

        Args:
            machine_id: The machine's device ID.
            limit: Maximum number of alerts.

        Returns:
            List of alerts.
        """
        try:
            from magenta.integration.defender import defender_connector
            result = await defender_connector.list_alerts(machine_id, limit=limit)
            return {"status": "success", "alerts": result, "count": len(result)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def isolate_machine(self, machine_id: str, reason: str = "") -> dict:
        """Isolate a machine in Defender.

        Args:
            machine_id: The machine's device ID.
            reason: Reason for isolation.

        Returns:
            Isolation result.
        """
        try:
            from magenta.integration.defender import defender_connector
            from magenta.core.models import ActionType
            result = await defender_connector.execute_action(
                ActionType.isolate_host, machine_id, {"reason": reason}
            )
            return {"status": "isolated", "machine_id": machine_id, "result": str(result)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def get_machine_health(self, machine_id: str) -> dict:
        """Get the health status of a Defender-managed machine.

        Args:
            machine_id: The machine's device ID.

        Returns:
            Health details.
        """
        try:
            from magenta.integration.defender import defender_connector
            result = await defender_connector.get_machine_health(machine_id)
            return {"status": "success", "health": result}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def get_tools(self) -> list[dict]:
        """Return MCP tool definitions for this server."""
        return [
            {
                "name": "get_machine",
                "description": "Get Defender machine details",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "machine_id": {"type": "string"},
                    },
                    "required": ["machine_id"],
                },
            },
            {
                "name": "list_machine_alerts",
                "description": "List alerts for a specific Defender machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "machine_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["machine_id"],
                },
            },
            {
                "name": "isolate_machine",
                "description": "Isolate a machine in Defender",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "machine_id": {"type": "string"},
                        "reason": {"type": "string", "default": ""},
                    },
                    "required": ["machine_id"],
                },
            },
            {
                "name": "get_machine_health",
                "description": "Get the health status of a Defender-managed machine",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "machine_id": {"type": "string"},
                    },
                    "required": ["machine_id"],
                },
            },
        ]


defender_mcp = DefenderMCPServer()
