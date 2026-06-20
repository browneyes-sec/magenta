"""MCP Tool Registry — wraps existing MCP servers as LangChain StructuredTools.

Zero new dependencies. Uses only what's already in pyproject.toml:
  - langchain (for StructuredTool)
  - httpx (already used by MCP servers)

Each tool maps to an existing MCP server function in:
  - magenta/mcp/sentinel_mcp_server.py
  - magenta/mcp/entra_mcp_server.py
  - magenta/mcp/defender_mcp_server.py
  - magenta/mcp/datalake_mcp_server.py
  - magenta/mcp/artifacts_mcp_server.py
  - magenta/mcp/registry_mcp_server.py
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Lazy imports — degrade if langchain not available ──────────────────

try:
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    logger.warning("langchain_core not available — MCP tools unavailable")


# ── Input schemas (Pydantic) ──────────────────────────────────────────

if HAS_LANGCHAIN:

    class SentinelQueryInput(BaseModel):
        workspace_id: str = Field(description="Sentinel workspace ID")
        query: str = Field(description="KQL query string")

    class SentinelAlertInput(BaseModel):
        workspace_id: str = Field(description="Sentinel workspace ID")
        alert_id: str = Field(description="Alert SystemAlertId")

    class SentinelAlertsInput(BaseModel):
        workspace_id: str = Field(description="Sentinel workspace ID")
        limit: int = Field(default=20, description="Max alerts to return")

    class EntraUserInput(BaseModel):
        user_id: str = Field(description="Entra ID user ID or UPN")

    class EntraRiskInput(BaseModel):
        user_id: str = Field(description="Entra ID user ID")

    class DefenderAlertInput(BaseModel):
        alert_id: str = Field(description="Defender alert ID")

    class DefenderIsolateInput(BaseModel):
        host_id: str = Field(description="Device ID to isolate")

    class DefenderMachineInput(BaseModel):
        machine_id: str = Field(description="Machine ID")

    class DatalakeSearchInput(BaseModel):
        query: str = Field(description="Search query")
        index: str = Field(default="default", description="Search index")
        limit: int = Field(default=50, description="Max results")

    class DatalakeMitreInput(BaseModel):
        technique_id: str = Field(description="MITRE technique ID (e.g., T1566)")

    class ArtifactSaveInput(BaseModel):
        mission_id: str = Field(description="Mission ID")
        artifact_type: str = Field(description="Type of artifact")
        content: str = Field(description="Artifact content")

    class ArtifactGetInput(BaseModel):
        mission_id: str = Field(description="Mission ID")
        artifact_type: str = Field(description="Type of artifact")


# ── Tool implementations (thin wrappers around existing MCP servers) ───

async def _sentinel_query_logs(workspace_id: str, query: str) -> dict:
    """Query Sentinel logs via KQL."""
    try:
        from magenta.mcp.sentinel_mcp_server import SentinelMCPServer
        server = SentinelMCPServer()
        return await server.run_kql_query(workspace_id, query)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _sentinel_get_alert(workspace_id: str, alert_id: str) -> dict:
    """Get a specific Sentinel alert."""
    try:
        from magenta.mcp.sentinel_mcp_server import SentinelMCPServer
        server = SentinelMCPServer()
        return await server.get_alert(workspace_id, alert_id)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _sentinel_list_alerts(workspace_id: str, limit: int = 20) -> dict:
    """List active Sentinel alerts."""
    try:
        from magenta.mcp.sentinel_mcp_server import SentinelMCPServer
        server = SentinelMCPServer()
        return await server.list_active_alerts(workspace_id, limit)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _entra_get_user(user_id: str) -> dict:
    """Get Entra ID user info."""
    try:
        from magenta.mcp.entra_mcp_server import EntraMCPServer
        server = EntraMCPServer()
        return await server.get_user(user_id)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _entra_get_risk(user_id: str) -> dict:
    """Get user risk level from Entra ID."""
    try:
        from magenta.mcp.entra_mcp_server import EntraMCPServer
        server = EntraMCPServer()
        return await server.get_user_risk(user_id)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _defender_get_alert(alert_id: str) -> dict:
    """Get Defender for Endpoint alert."""
    try:
        from magenta.mcp.defender_mcp_server import DefenderMCPServer
        server = DefenderMCPServer()
        return await server.get_alert(alert_id)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _defender_isolate_host(host_id: str) -> dict:
    """Isolate a host in Defender for Endpoint."""
    try:
        from magenta.mcp.defender_mcp_server import DefenderMCPServer
        server = DefenderMCPServer()
        return await server.isolate_machine(host_id)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _defender_get_machine(machine_id: str) -> dict:
    """Get machine details from Defender."""
    try:
        from magenta.mcp.defender_mcp_server import DefenderMCPServer
        server = DefenderMCPServer()
        return await server.get_machine(machine_id)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _datalake_search(query: str, index: str = "default", limit: int = 50) -> dict:
    """Search the data lake."""
    try:
        from magenta.mcp.datalake_mcp_server import DataLakeMCPServer
        server = DataLakeMCPServer()
        return await server.search(query, index, limit)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _datalake_mitre_lookup(technique_id: str) -> dict:
    """Lookup MITRE technique in data lake."""
    try:
        from magenta.mcp.datalake_mcp_server import DataLakeMCPServer
        server = DataLakeMCPServer()
        return await server.mitre_lookup(technique_id)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _artifacts_save(mission_id: str, artifact_type: str, content: str) -> dict:
    """Save an artifact to the artifact store."""
    try:
        from magenta.mcp.artifacts_mcp_server import ArtifactsMCPServer
        server = ArtifactsMCPServer()
        return await server.save_artifact(mission_id, artifact_type, content)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _artifacts_get(mission_id: str, artifact_type: str) -> dict:
    """Retrieve an artifact from the artifact store."""
    try:
        from magenta.mcp.artifacts_mcp_server import ArtifactsMCPServer
        server = ArtifactsMCPServer()
        return await server.get_artifact(mission_id, artifact_type)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ── Tool registry ──────────────────────────────────────────────────────
#
# Maps tool names → (handler, schema, domain).
# Used by:
#   1. LangGraph subgraphs (get_tools_for_subgraph)
#   2. Future: MCP server for external consumers

MCP_TOOLS: dict[str, dict] = {}

if HAS_LANGCHAIN:
    MCP_TOOLS = {
        # Sentinel
        "sentinel_query_logs": {
            "handler": _sentinel_query_logs,
            "schema": SentinelQueryInput,
            "domain": "sentinel",
            "description": "Run a KQL query against Microsoft Sentinel logs",
        },
        "sentinel_get_alert": {
            "handler": _sentinel_get_alert,
            "schema": SentinelAlertInput,
            "domain": "sentinel",
            "description": "Get a specific Sentinel alert by SystemAlertId",
        },
        "sentinel_list_alerts": {
            "handler": _sentinel_list_alerts,
            "schema": SentinelAlertsInput,
            "domain": "sentinel",
            "description": "List active Sentinel alerts",
        },
        # Entra ID
        "entra_get_user": {
            "handler": _entra_get_user,
            "schema": EntraUserInput,
            "domain": "entra",
            "description": "Get Entra ID user info and risk assessment",
        },
        "entra_get_risk": {
            "handler": _entra_get_risk,
            "schema": EntraRiskInput,
            "domain": "entra",
            "description": "Get user risk level from Entra ID Protection",
        },
        # Defender
        "defender_get_alert": {
            "handler": _defender_get_alert,
            "schema": DefenderAlertInput,
            "domain": "defender",
            "description": "Get Defender for Endpoint alert details",
        },
        "defender_isolate_host": {
            "handler": _defender_isolate_host,
            "schema": DefenderIsolateInput,
            "domain": "defender",
            "description": "Isolate a host in Defender for Endpoint",
        },
        "defender_get_machine": {
            "handler": _defender_get_machine,
            "schema": DefenderMachineInput,
            "domain": "defender",
            "description": "Get machine details from Defender",
        },
        # Data Lake
        "datalake_search": {
            "handler": _datalake_search,
            "schema": DatalakeSearchInput,
            "domain": "datalake",
            "description": "Search the security data lake",
        },
        "datalake_mitre_lookup": {
            "handler": _datalake_mitre_lookup,
            "schema": DatalakeMitreInput,
            "domain": "datalake",
            "description": "Lookup MITRE ATT&CK technique in the data lake",
        },
        # Artifacts
        "artifacts_save": {
            "handler": _artifacts_save,
            "schema": ArtifactSaveInput,
            "domain": "artifacts",
            "description": "Save an investigation artifact",
        },
        "artifacts_get": {
            "handler": _artifacts_get,
            "schema": ArtifactGetInput,
            "domain": "artifacts",
            "description": "Retrieve an investigation artifact",
        },
    }


# ── Subgraph tool mapping ─────────────────────────────────────────────
#
# Which tools each subgraph needs. Keeps subgraphs focused on their
# domain and avoids loading unnecessary MCP connections.

SUBGRAPH_TOOL_MAP: dict[str, list[str]] = {
    "triage": [
        "sentinel_query_logs",
        "sentinel_get_alert",
        "datalake_mitre_lookup",
    ],
    "investigation": [
        "sentinel_query_logs",
        "datalake_search",
        "entra_get_user",
        "defender_get_alert",
        "defender_get_machine",
    ],
    "containment": [
        "defender_isolate_host",
        "entra_get_user",
        "entra_get_risk",
    ],
    "compliance": [
        "artifacts_save",
        "artifacts_get",
    ],
}


def get_tools_for_subgraph(subgraph_name: str) -> list["StructuredTool"]:
    """Get LangChain StructuredTool instances for a subgraph.

    Returns empty list if langchain unavailable or no tools mapped.
    """
    if not HAS_LANGCHAIN:
        return []

    tool_names = SUBGRAPH_TOOL_MAP.get(subgraph_name, [])
    tools = []

    for name in tool_names:
        tool_def = MCP_TOOLS.get(name)
        if not tool_def:
            continue
        try:
            tool = StructuredTool.from_function(
                coroutine=tool_def["handler"],
                name=name,
                description=tool_def["description"],
                args_schema=tool_def["schema"],
            )
            tools.append(tool)
        except Exception as exc:
            logger.warning("Failed to create tool %s: %s", name, exc)

    return tools


def list_tools() -> list[dict]:
    """List all registered MCP tools (for API/docs)."""
    return [
        {
            "name": name,
            "domain": defn["domain"],
            "description": defn["description"],
        }
        for name, defn in MCP_TOOLS.items()
    ]
