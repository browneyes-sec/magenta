"""MCP server — Mission, agent, and directive registry search."""


class RegistryMCPServer:
    """MCP tools for Magenta registry searches."""

    def __init__(self):
        self.name = "registry"
        self.description = "Mission, agent, and directive registry search MCP tools"

    async def search_missions(self, query: str = "", status: str = "") -> dict:
        """Search missions by query or status.

        Args:
            query: Free-text search string.
            status: Filter by mission status.

        Returns:
            Matching missions.
        """
        try:
            from magenta.data.sql.mission_repo import mission_repository

            missions = await mission_repository.search(query=query, status=status)
            return {
                "status": "success",
                "missions": [m.model_dump() for m in missions],
                "count": len(missions),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def get_mission(self, mission_id: str) -> dict:
        """Get a mission by ID.

        Args:
            mission_id: The mission ID.

        Returns:
            Mission details.
        """
        try:
            from magenta.data.sql.mission_repo import mission_repository

            mission = await mission_repository.get_by_id(mission_id)
            if not mission:
                return {"status": "not_found", "mission_id": mission_id}
            return {"status": "success", "mission": mission.model_dump()}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def list_active_missions(self) -> dict:
        """List all active missions.

        Returns:
            List of active missions.
        """
        return await self.search_missions(status="active")

    async def get_dictator_status(self) -> dict:
        """Get the current Dictator super-agent status.

        Returns:
            Dictator status details.
        """
        from magenta.agents.dictator import dictator

        return await dictator.get_framework_status()

    async def search_directives(self, limit: int = 50) -> dict:
        """Get the recent directive log.

        Args:
            limit: Maximum number of directives.

        Returns:
            Recent directive entries.
        """
        from magenta.dictator.state import dictator_state

        directives = dictator_state.directive_log[-limit:]
        return {"status": "success", "directives": directives, "count": len(directives)}

    async def get_agent_summary(self) -> dict:
        """Get a summary of all registered agents.

        Returns:
            Agent count and status breakdown.
        """
        try:
            from magenta.agents.registry import agent_registry

            agents = agent_registry.list_agents()
            return {
                "status": "success",
                "total": len(agents),
                "agents": [{"id": a.agent_id, "role": a.role} for a in agents],
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def get_tools(self) -> list[dict]:
        """Return MCP tool definitions for this server."""
        return [
            {
                "name": "search_missions",
                "description": "Search missions by query or status",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "default": ""},
                        "status": {"type": "string", "default": ""},
                    },
                },
            },
            {
                "name": "get_mission",
                "description": "Get a mission by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "mission_id": {"type": "string"},
                    },
                    "required": ["mission_id"],
                },
            },
            {
                "name": "list_active_missions",
                "description": "List all active missions",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_dictator_status",
                "description": "Get the current Dictator super-agent status",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "search_directives",
                "description": "Get the recent directive log",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 50},
                    },
                },
            },
            {
                "name": "get_agent_summary",
                "description": "Get a summary of all registered agents",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]


registry_mcp = RegistryMCPServer()
