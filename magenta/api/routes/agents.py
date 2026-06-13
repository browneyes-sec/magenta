"""API routes — agents management."""

from fastapi import APIRouter, HTTPException
from typing import list

from magenta.core.models import AgentConfig
from magenta.core.agent import agent_registry
from magenta.api.deps import get_agent_registry

router = APIRouter()


@router.get("/")
async def list_agents():
    """List all registered agents."""
    agents = agent_registry.all_agents()
    return [
        {
            "agent_id": a.agent_id,
            "role": a.role,
            "status": a.status.value,
            "model": f"{a.config.model_provider}/{a.config.model_name}",
        }
        for a in agents
    ]


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details."""
    agent = agent_registry.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "agent_id": agent.agent_id,
        "role": agent.role,
        "status": agent.status.value,
        "config": agent.config.model_dump(),
    }


@router.get("/roles/{role}")
async def get_agents_by_role(role: str):
    """Get agents by role."""
    agents = agent_registry.get_by_role(role)
    return [
        {
            "agent_id": a.agent_id,
            "status": a.status.value,
            "load": a.turn_count,
        }
        for a in agents
    ]


@router.post("/register")
async def register_agent(config: AgentConfig):
    """Register a new agent."""
    from magenta.agents.base import LLMAgent
    agent = LLMAgent(config)
    agent_registry.register(agent)
    return {"status": "registered", "agent_id": config.agent_id}
