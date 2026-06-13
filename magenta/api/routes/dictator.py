"""API routes — Dictator super-agent oversight and directives."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from magenta.agents.dictator import dictator
from magenta.dictator.directives import DirectiveType
from magenta.dictator.policies import OrchestrationPolicy

router = APIRouter()


@router.get("/status")
async def get_dictator_status():
    """Get Dictator and framework status."""
    return await dictator.get_framework_status()


@router.get("/oversight")
async def get_oversight_board():
    """Get the full Dictator oversight board."""
    return await dictator.get_oversight_board()


@router.get("/oversight/{mission_id}")
async def get_mission_oversight(mission_id: str):
    """Get oversight details for a specific mission."""
    result = await dictator.get_mission_oversight(mission_id)
    if not result:
        raise HTTPException(status_code=404, detail="Mission not found under Dictator oversight")
    return result


@router.get("/directives")
async def get_directives(limit: int = Query(50, ge=1, le=500)):
    """Get the Dictator directive log."""
    return await dictator.get_directive_log(limit=limit)


@router.post("/directives")
async def issue_directive(
    directive_type: str,
    target: str,
    mission_id: Optional[str] = None,
    payload: dict = {},
    reason: str = "",
):
    """Issue a new Dictator directive."""
    try:
        dtype = DirectiveType(directive_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid directive type: {directive_type}")

    directive = await dictator.issue_directive(
        dtype=dtype,
        target=target,
        mission_id=mission_id,
        payload=payload,
        reason=reason,
    )
    return {"directive_id": directive.directive_id, "status": "issued"}


@router.post("/halt/{mission_id}")
async def halt_mission(mission_id: str, reason: str = "API override"):
    """Halt a running mission."""
    return await dictator.halt_mission(mission_id, reason)


@router.post("/escalate/{mission_id}")
async def escalate_mission(mission_id: str, reason: str = ""):
    """Escalate a mission to human operators."""
    return await dictator.escalate_mission(mission_id, reason)


@router.post("/deploy/{role}")
async def deploy_agent(role: str, model: Optional[str] = None):
    """Deploy a new agent by role."""
    kwargs = {}
    if model:
        kwargs["model_name"] = model
    agent = await dictator.deploy_agent(role, **kwargs)
    return {
        "status": "deployed",
        "agent_id": agent.agent_id,
        "role": agent.role,
        "model": f"{agent.config.model_provider}/{agent.config.model_name}",
    }


@router.delete("/agents/{agent_id}")
async def recall_agent(agent_id: str):
    """Recall (unregister) an agent."""
    result = await dictator.recall_agent(agent_id)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "recalled", "agent_id": agent_id}


@router.post("/teaming/{mission_id}")
async def override_teaming(mission_id: str, structure: str):
    """Override the teaming structure for a mission."""
    valid_structures = ["pipeline", "supervisor", "debate", "mesh", "referee"]
    if structure not in valid_structures:
        raise HTTPException(status_code=400, detail=f"Invalid structure. Must be one of: {valid_structures}")
    return await dictator.override_teaming(mission_id, structure)


@router.post("/policies/override")
async def apply_policy_override(policy: OrchestrationPolicy):
    """Apply a temporary policy override."""
    return await dictator.apply_policy_override(policy)


@router.delete("/policies/overrides")
async def clear_policy_overrides():
    """Clear all active policy overrides."""
    return await dictator.clear_policy_overrides()


@router.get("/policies")
async def list_policies():
    """List all orchestration policies."""
    from magenta.dictator.policies import policy_engine
    return {
        "policies": [p.model_dump() for p in policy_engine._policies],
        "overrides": {n: p.model_dump() for n, p in policy_engine._overrides.items()},
    }


@router.post("/probes/promote")
async def promote_probe(name: str, guard: bool = False):
    """Promote a probe, optionally to an enforcement guard."""
    return await dictator.promote_probe(name, guard=guard)


@router.get("/framework")
async def framework_status():
    """Get comprehensive framework status."""
    return await dictator.get_framework_status()
