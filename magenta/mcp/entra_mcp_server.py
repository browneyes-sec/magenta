"""MCP server — Microsoft Entra ID user, group, and device lookups."""

from typing import Optional


class EntraMCPServer:
    """MCP tools for Microsoft Entra ID operations."""

    def __init__(self):
        self.name = "entra"
        self.description = "Microsoft Entra ID MCP tools"

    async def get_user(self, user_id: str) -> dict:
        """Get Entra ID user details.

        Args:
            user_id: The user's object ID or UPN.

        Returns:
            User details from Entra ID.
        """
        try:
            from magenta.integration.entra import entra_connector
            result = await entra_connector.get_user(user_id)
            return {"status": "success", "user": result}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def list_group_members(self, group_id: str) -> dict:
        """List all members of an Entra ID group.

        Args:
            group_id: The group's object ID.

        Returns:
            List of group members.
        """
        try:
            from magenta.integration.entra import entra_connector
            result = await entra_connector.list_group_members(group_id)
            return {"status": "success", "members": result, "count": len(result)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def get_device(self, device_id: str) -> dict:
        """Get Entra ID device details.

        Args:
            device_id: The device's object ID.

        Returns:
            Device details.
        """
        try:
            from magenta.integration.entra import entra_connector
            result = await entra_connector.get_device(device_id)
            return {"status": "success", "device": result}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def search_user(self, query: str) -> dict:
        """Search for users in Entra ID.

        Args:
            query: Search string (display name, email, or UPN).

        Returns:
            Matching users.
        """
        try:
            from magenta.integration.entra import entra_connector
            result = await entra_connector.search_users(query)
            return {"status": "success", "users": result, "count": len(result)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def get_tools(self) -> list[dict]:
        """Return MCP tool definitions for this server."""
        return [
            {
                "name": "get_user",
                "description": "Get Entra ID user details",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "User object ID or UPN"},
                    },
                    "required": ["user_id"],
                },
            },
            {
                "name": "list_group_members",
                "description": "List all members of an Entra ID group",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string", "description": "Group object ID"},
                    },
                    "required": ["group_id"],
                },
            },
            {
                "name": "get_device",
                "description": "Get Entra ID device details",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Device object ID"},
                    },
                    "required": ["device_id"],
                },
            },
            {
                "name": "search_user",
                "description": "Search for users in Entra ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search string"},
                    },
                    "required": ["query"],
                },
            },
        ]


entra_mcp = EntraMCPServer()
