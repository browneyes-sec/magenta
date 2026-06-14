"""MCP server — Data Lake artifact store read/write operations."""

from typing import Any, Optional


class DataLakeMCPServer:
    """MCP tools for Data Lake artifact storage."""

    def __init__(self):
        self.name = "datalake"
        self.description = "Data Lake artifact store MCP tools"

    async def list_artifacts(self, prefix: str = "", limit: int = 50) -> dict:
        """List artifacts in the data lake.

        Args:
            prefix: Optional path prefix to filter by.
            limit: Maximum number of artifacts.

        Returns:
            List of artifacts with metadata.
        """
        try:
            from magenta.data.lake.client import lake_client
            result = await lake_client.list_blobs(prefix=prefix, limit=limit)
            return {"status": "success", "artifacts": result, "count": len(result)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def get_artifact(self, path: str) -> dict:
        """Read an artifact from the data lake.

        Args:
            path: Full path to the artifact.

        Returns:
            Artifact content and metadata.
        """
        try:
            from magenta.data.lake.client import lake_client
            content = await lake_client.read_blob(path)
            return {"status": "success", "path": path, "content": str(content)[:10000]}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def save_artifact(self, path: str, content: str, content_type: str = "text/plain") -> dict:
        """Save an artifact to the data lake.

        Args:
            path: Destination path in the lake.
            content: Artifact content.
            content_type: MIME type.

        Returns:
            Write result.
        """
        try:
            from magenta.data.lake.client import lake_client
            await lake_client.write_blob(path, content.encode(), content_type=content_type)
            return {"status": "saved", "path": path, "size_bytes": len(content.encode())}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def delete_artifact(self, path: str) -> dict:
        """Delete an artifact from the data lake.

        Args:
            path: Full path to the artifact.

        Returns:
            Delete result.
        """
        try:
            from magenta.data.lake.client import lake_client
            await lake_client.delete_blob(path)
            return {"status": "deleted", "path": path}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def get_tools(self) -> list[dict]:
        """Return MCP tool definitions for this server."""
        return [
            {
                "name": "list_artifacts",
                "description": "List artifacts in the data lake",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prefix": {"type": "string", "default": ""},
                        "limit": {"type": "integer", "default": 50},
                    },
                },
            },
            {
                "name": "get_artifact",
                "description": "Read an artifact from the data lake",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "save_artifact",
                "description": "Save an artifact to the data lake",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "content_type": {"type": "string", "default": "text/plain"},
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "delete_artifact",
                "description": "Delete an artifact from the data lake",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
        ]


datalake_mcp = DataLakeMCPServer()
