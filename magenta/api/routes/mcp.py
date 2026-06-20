"""MCP Bridge Routes — /mcp/* endpoints for MCPO proxy."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/mcp", tags=["mcp"])

CATALOG_PATH = Path("/app/soa/services/catalog.toml")


def _load_catalog() -> dict:
    """Load MCP service catalog."""
    try:
        with open(CATALOG_PATH, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {
            "schema": {"version": "1.0"},
            "services": [
                {
                    "id": "mcp-sentinel",
                    "description": "Microsoft Sentinel SIEM operations",
                    "transport": "grpc",
                    "port": 50051,
                    "tools": ["sentinel_query_incidents", "sentinel_update_incident", "sentinel_get_alert", "sentinel_run_kql"],
                },
                {
                    "id": "mcp-entra-id",
                    "description": "Entra ID identity management",
                    "transport": "grpc",
                    "port": 50052,
                    "tools": ["entra_disable_account", "entra_get_user", "entra_list_groups", "entra_get_signin_logs"],
                },
                {
                    "id": "mcp-defender",
                    "description": "Microsoft Defender ATP EDR operations",
                    "transport": "grpc",
                    "port": 50053,
                    "tools": ["defender_isolate_host", "defender_run_scan", "defender_get_alerts", "defender_list_devices"],
                },
                {
                    "id": "mcp-threat-intel",
                    "description": "Threat intelligence lookups (VT, Shodan, OTX)",
                    "transport": "http",
                    "port": 50054,
                    "tools": ["ti_scan_url", "ti_scan_hash", "ti_get_ip_reputation", "ti_get_domain_info"],
                },
                {
                    "id": "mcp-servicenow",
                    "description": "ServiceNow ITSM operations",
                    "transport": "grpc",
                    "port": 50055,
                    "tools": ["servicenow_create_ticket", "servicenow_update_ticket", "servicenow_query_cmdb"],
                },
                {
                    "id": "mcp-data-mesh",
                    "description": "Vectorized data mesh — unified query & ingestion",
                    "transport": "http",
                    "port": 8000,
                    "tools": ["mesh_query", "mesh_ingest", "mesh_list_products", "mesh_health"],
                },
                {
                    "id": "mcp-agent-ops",
                    "description": "Agent Ops — configuration analysis, IaC, multi-cloud, FinOps",
                    "transport": "grpc",
                    "port": 50060,
                    "tools": ["config_analyze", "config_validate", "config_audit", "config_reconcile", "config_diff", "iac_plan", "iac_apply", "iac_drift_detect", "iac_state_inspect", "iac_destroy", "cloud_provision", "cloud_discover_resources", "cloud_migrate", "cloud_health", "finops_cost_analysis", "finops_recommend_rightsize", "finops_forecast", "finops_enforce_budget", "finops_tag_compliance"],
                },
                {
                    "id": "mcp-orchestrator",
                    "description": "Swarm orchestrator — mission lifecycle & agent assignment",
                    "transport": "grpc",
                    "port": 50061,
                    "tools": ["orchestrator_create_mission", "orchestrator_assign_agent", "orchestrator_track_progress", "orchestrator_escalate"],
                },
                {
                    "id": "mcp-finops",
                    "description": "Financial operations — cost tracking & optimization",
                    "transport": "http",
                    "port": 50062,
                    "tools": ["finops_get_costs", "finops_get_budget_status", "finops_get_recommendations", "finops_get_anomalies"],
                },
            ],
        }


@router.get("/registry")
async def mcp_registry():
    """Registry endpoint for mission, agent, directive search."""
    from magenta.api.routes import dictator as dictator_routes
    from magenta.api.routes import missions as missions_routes

    missions_data = await missions_routes.list_missions(limit=50)
    dictator_status = await dictator_routes.get_dictator_status()
    catalog = _load_catalog()

    services = catalog.get("services", [])
    agents_by_role = {}
    for svc in services:
        if svc.get("id", "").startswith("mcp-"):
            role = svc["id"].replace("mcp-", "")
            agents_by_role[role] = {
                "tools": svc.get("tools", []),
                "transport": svc.get("transport"),
                "port": svc.get("port"),
            }

    return {
        "missions": missions_data,
        "dictator": dictator_status,
        "agents_by_role": agents_by_role,
        "total_agents": len(agents_by_role),
        "services": services,
    }


@router.get("/artifacts")
async def mcp_artifacts():
    """Artifact generator endpoint for HTML dashboard generation."""
    return {
        "directive_timeline": {"type": "html", "description": "Directive timeline dashboard"},
        "mission_throughput": {"type": "html", "description": "Mission throughput chart"},
        "policy_status": {"type": "html", "description": "Policy status dashboard"},
        "dead_letter": {"type": "html", "description": "Dead letter queue dashboard"},
        "threat_analytics": {"type": "html", "description": "Threat analytics dashboard"},
        "blue_team_ops": {"type": "html", "description": "Blue team operations dashboard"},
    }


@router.get("/health")
async def mcp_health():
    """MCP health check."""
    catalog = _load_catalog()
    services = catalog.get("services", [])
    return {
        "status": "healthy",
        "services": ["registry", "artifacts"],
        "registered_services": len(services),
        "catalog_version": catalog.get("schema", {}).get("version", "unknown"),
    }


@router.get("/discover")
async def mcp_discover():
    """MCP server discovery."""
    catalog = _load_catalog()
    services = catalog.get("services", [])

    servers = {}
    for svc in services:
        svc_id = svc.get("id", "")
        if svc_id:
            servers[svc_id] = {
                "name": svc_id.replace("mcp-", "").replace("-", " ").title(),
                "description": svc.get("description", ""),
                "url": f"/mcp/{svc_id}",
                "transport": svc.get("transport"),
                "port": svc.get("port"),
                "tools": svc.get("tools", []),
            }

    return {"servers": servers}
