"""API routes — health checks."""

from fastapi import APIRouter
from datetime import datetime

from magenta.core.agent import agent_registry
from magenta.models.router import model_router

router = APIRouter()


@router.get("/")
async def full_health():
    """Full system health check."""
    agents = agent_registry.all_agents()
    models = model_router.get_available_models()

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "checks": {
            "agents": {
                "status": "healthy",
                "count": len(agents),
                "by_role": agent_registry.counts,
            },
            "models": {
                "status": "healthy",
                "available": len(models),
            },
            "pipeline": {
                "status": "healthy",
                "message": "Event Hubs stub — no actual connection",
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
        "by_role": agent_registry.counts,
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
