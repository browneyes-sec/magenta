"""MCP tool registry — wraps existing MCP servers as LangChain StructuredTools."""

from magenta.workflows.mcp.tool_registry import MCP_TOOLS, get_tools_for_subgraph

__all__ = ["MCP_TOOLS", "get_tools_for_subgraph"]
