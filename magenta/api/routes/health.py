"""API routes — health checks."""

from datetime import datetime

from fastapi import APIRouter

from magenta.core.agent import agent_registry
from magenta.core.mission import mission_manager
from magenta.models.router import model_router
from magenta.workflows.engine import workflow_engine

router = APIRouter()


@router.get("/")
async def full_health():
    """Full system health check."""
    agents = agent_registry.all_agents()
    models = model_router.get_available_models()

    # Workflow engine health
    active_workflows = len(workflow_engine._running_missions)
    total_executions = len(workflow_engine._executions)
    pending_approvals = sum(len(e.approvals_pending) for e in workflow_engine._executions.values())

    # Mission manager health
    active_missions = mission_manager.active_count()
    total_missions = len(mission_manager._missions)

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
            "workflows": {
                "status": "healthy",
                "active_executions": active_workflows,
                "total_executions": total_executions,
                "pending_approvals": pending_approvals,
            },
            "missions": {
                "status": "healthy",
                "active_missions": active_missions,
                "total_missions": total_missions,
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
