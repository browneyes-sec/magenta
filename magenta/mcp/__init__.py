"""MCP (Model Context Protocol) servers for Magenta ASOAR framework.

Each module exposes a set of MCP tools callable by LLM agents
through the MCP Orchestrator (MCPO) proxy.
"""

from magenta.mcp.sentinel_mcp_server import SentinelMCPServer, sentinel_mcp
from magenta.mcp.entra_mcp_server import EntraMCPServer, entra_mcp
from magenta.mcp.defender_mcp_server import DefenderMCPServer, defender_mcp
from magenta.mcp.datalake_mcp_server import DataLakeMCPServer, datalake_mcp
from magenta.mcp.registry_mcp_server import RegistryMCPServer, registry_mcp
from magenta.mcp.artifacts_mcp_server import ArtifactsMCPServer, artifacts_mcp

__all__ = [
    "SentinelMCPServer",
    "sentinel_mcp",
    "EntraMCPServer",
    "entra_mcp",
    "DefenderMCPServer",
    "defender_mcp",
    "DataLakeMCPServer",
    "datalake_mcp",
    "RegistryMCPServer",
    "registry_mcp",
    "ArtifactsMCPServer",
    "artifacts_mcp",
]
