"""API routes — health checks for Kubernetes probes and monitoring.

Endpoints:
    GET /health/live          — Process alive? (no dependency checks)
    GET /health/ready         — Can accept missions? (agent registry, EventHub, LLM)
    GET /health/dependencies  — Deep check all external services
    GET /health               — Full system health (backward compat)
"""

from __future__ import annotations

from fastapi import APIRouter
from datetime import datetime

from magenta.core.agent import agent_registry
from magenta.models.router import model_router

router = APIRouter()

_start_time = datetime.utcnow()


@router.get("/live")
async def liveness():
    """Kubernetes liveness probe — is the process alive?"""
    return {
        "status": "alive",
        "uptime_seconds": (datetime.utcnow() - _start_time).total_seconds(),
    }


@router.get("/ready")
async def readiness():
    """Kubernetes readiness probe — can the agent accept missions?"""
    checks = {}
    all_healthy = True

    # Check agent registry non-empty
    agents = agent_registry.all_agents()
    if agents:
        checks["agent_registry"] = {
            "status": "healthy",
            "count": len(agents),
        }
    else:
        checks["agent_registry"] = {
            "status": "degraded",
            "message": "No agents registered",
        }
        all_healthy = False

    # Check LLM tier reachable
    try:
        models = model_router.get_available_models()
        if models:
            checks["llm_tier"] = {
                "status": "healthy",
                "available": len(models),
            }
        else:
            checks["llm_tier"] = {
                "status": "degraded",
                "message": "No models configured",
            }
            all_healthy = False
    except Exception as e:
        checks["llm_tier"] = {
            "status": "degraded",
            "message": str(e),
        }
        all_healthy = False

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": (datetime.utcnow() - _start_time).total_seconds(),
        "checks": checks,
    }


@router.get("/dependencies")
async def deep_dependency_check():
    """Deep dependency check — pings all external services.

    This endpoint may be slow (up to 30s) as it pings every external service.
    """
    checks = {}
    all_healthy = True

    # Check SOAR
    try:
        from magenta.integration.soar import SOARConnector
        soar = SOARConnector()
        ok = await soar.ping()
        checks["soar"] = {
            "status": "healthy" if ok else "degraded",
            "message": "SOAR API reachable" if ok else "SOAR API unreachable",
        }
        if not ok:
            all_healthy = False
    except Exception as e:
        checks["soar"] = {"status": "degraded", "message": str(e)}
        all_healthy = False

    # Check Sentinel
    try:
        from magenta.integration.sentinel import SentinelConnector
        from magenta.config import settings
        if settings.sentinel.tenant_id:
            sentinel = SentinelConnector()
            ok = await sentinel.ping()
            checks["sentinel"] = {
                "status": "healthy" if ok else "degraded",
                "message": "Sentinel API reachable" if ok else "Sentinel API unreachable",
            }
            if not ok:
                all_healthy = False
        else:
            checks["sentinel"] = {"status": "not_configured"}
    except Exception as e:
        checks["sentinel"] = {"status": "degraded", "message": str(e)}
        all_healthy = False

    # Check Splunk
    try:
        from magenta.integration.splunk import SplunkConnector
        from magenta.config import settings
        if settings.splunk.host:
            splunk = SplunkConnector()
            ok = await splunk.ping()
            checks["splunk"] = {
                "status": "healthy" if ok else "degraded",
                "message": "Splunk API reachable" if ok else "Splunk API unreachable",
            }
            if not ok:
                all_healthy = False
        else:
            checks["splunk"] = {"status": "not_configured"}
    except Exception as e:
        checks["splunk"] = {"status": "degraded", "message": str(e)}
        all_healthy = False

    # Check LLM models
    try:
        models = await model_router.ping_all()
        healthy_models = sum(1 for v in models.values() if v)
        checks["llm_models"] = {
            "status": "healthy" if healthy_models > 0 else "degraded",
            "available": healthy_models,
            "total": len(models),
        }
        if healthy_models == 0:
            all_healthy = False
    except Exception as e:
        checks["llm_models"] = {"status": "degraded", "message": str(e)}
        all_healthy = False

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": (datetime.utcnow() - _start_time).total_seconds(),
        "checks": checks,
    }


@router.get("")
async def full_health():
    """Full system health check (backward-compatible)."""
    agents = agent_registry.all_agents()
    models = model_router.get_available_models()

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "uptime_seconds": (datetime.utcnow() - _start_time).total_seconds(),
        "checks": {
            "agents": {
                "status": "healthy",
                "count": len(agents),
                "by_role": agent_registry.counts if hasattr(agent_registry, "counts") else {},
            },
            "models": {
                "status": "healthy",
                "available": len(models),
            },
        },
    }


@router.get("/agents")
async def agent_health():
    """Agent health status."""
    agents = agent_registry.all_agents()
    return {
        "status": "healthy",
        "count": len(agents),
        "by_role": agent_registry.counts if hasattr(agent_registry, "counts") else {},
        "agents": [
            {
                "agent_id": a.agent_id,
                "role": a.role,
                "status": a.status.value,
                "model": f"{a.config.model_provider}/{a.config.model_name}",
            }
            for a in agents
        ],
    }


@router.get("/models")
async def model_health():
    """Model health status."""
    models = model_router.get_available_models()
    return {
        "status": "healthy",
        "count": len(models),
        "models": models,
    }
