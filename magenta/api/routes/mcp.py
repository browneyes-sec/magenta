"""MCP Bridge Routes — /mcp/* endpoints for MCPO proxy."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/registry")
async def mcp_registry():
    """Registry endpoint for mission, agent, directive search."""
    from magenta.api.routes import dictator as dictator_routes
    from magenta.api.routes import missions as missions_routes

    missions_data = await missions_routes.list_missions()
    dictator_status = await dictator_routes.get_dictator_status()

    return {
        "missions": missions_data,
        "dictator": dictator_status,
        "agents_by_role": {},
        "total_agents": 0,
    }


@router.get("/artifacts")
async def mcp_artifacts():
    """Artifact generator endpoint for HTML dashboard generation."""
    return {
        "directive_timeline": {"type": "html", "description": "Directive timeline dashboard"},
        "mission_throughput": {"type": "html", "description": "Mission throughput chart"},
        "policy_status": {"type": "html", "description": "Policy status dashboard"},
        "dead_letter": {"type": "html", "description": "Dead letter queue dashboard"},
    }


@router.get("/health")
async def mcp_health():
    """MCP health check."""
    return {"status": "healthy", "services": ["registry", "artifacts"]}


@router.get("/discover")
async def mcp_discover():
    """MCP server discovery."""
    return {
        "servers": {
            "registry": {
                "name": "Registry",
                "description": "Mission, agent, directive search",
                "url": "/mcp/registry",
            },
            "artifacts": {
                "name": "Artifact Generator",
                "description": "HTML dashboard artifact generation",
                "url": "/mcp/artifacts",
            },
        }
    }
