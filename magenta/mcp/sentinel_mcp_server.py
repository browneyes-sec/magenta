"""MCP server — Microsoft Sentinel KQL queries and Log Ingestion API."""


class SentinelMCPServer:
    """MCP tools for Microsoft Sentinel operations."""

    def __init__(self):
        self.name = "sentinel"
        self.description = "Microsoft Sentinel MCP tools"

    async def run_kql_query(self, workspace_id: str, query: str) -> dict:
        """Run a KQL query against a Sentinel workspace.

        Args:
            workspace_id: The Sentinel workspace ID.
            query: The KQL query string.

        Returns:
            Query results as a dict with rows and columns.
        """
        try:
            from magenta.integration.sentinel import sentinel_connector

            result = await sentinel_connector.run_kql_query(workspace_id, query)
            return {
                "status": "success",
                "results": result,
                "row_count": len(result) if result else 0,
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def get_alert(self, workspace_id: str, alert_id: str) -> dict:
        """Get a specific Sentinel alert by ID.

        Args:
            workspace_id: The Sentinel workspace ID.
            alert_id: The alert ID to retrieve.

        Returns:
            Alert details.
        """
        query = f"""SecurityAlert
| where SystemAlertId == "{alert_id}"
| take 1"""
        return await self.run_kql_query(workspace_id, query)

    async def list_active_alerts(self, workspace_id: str, limit: int = 20) -> dict:
        """List active Sentinel alerts.

        Args:
            workspace_id: The Sentinel workspace ID.
            limit: Maximum number of alerts to return.

        Returns:
            List of active alerts.
        """
        query = f"""SecurityAlert
| where Status == "Active"
| order by TimeGenerated desc
| take {limit}"""
        return await self.run_kql_query(workspace_id, query)

    async def ingest_to_log_analytics(
        self, workspace_id: str, table: str, records: list[dict]
    ) -> dict:
        """Ingest data to a Log Analytics table via the Log Ingestion API.

        Args:
            workspace_id: The Sentinel workspace ID.
            table: The target table name.
            records: List of records to ingest.

        Returns:
            Ingestion result.
        """
        try:
            from magenta.integration.sentinel import sentinel_connector

            result = await sentinel_connector.ingest_logs(workspace_id, table, records)
            return {"status": "ingested", "record_count": len(records), "result": str(result)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def get_tools(self) -> list[dict]:
        """Return MCP tool definitions for this server."""
        return [
            {
                "name": "run_kql_query",
                "description": "Run a KQL query against a Sentinel workspace",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workspace_id": {"type": "string"},
                        "query": {"type": "string"},
                    },
                    "required": ["workspace_id", "query"],
                },
            },
            {
                "name": "get_alert",
                "description": "Get a specific Sentinel alert by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workspace_id": {"type": "string"},
                        "alert_id": {"type": "string"},
                    },
                    "required": ["workspace_id", "alert_id"],
                },
            },
            {
                "name": "list_active_alerts",
                "description": "List active Sentinel alerts",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workspace_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["workspace_id"],
                },
            },
            {
                "name": "ingest_to_log_analytics",
                "description": "Ingest data to a Log Analytics table",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workspace_id": {"type": "string"},
                        "table": {"type": "string"},
                        "records": {"type": "array", "items": {"type": "object"}},
                    },
                    "required": ["workspace_id", "table", "records"],
                },
            },
        ]


sentinel_mcp = SentinelMCPServer()
