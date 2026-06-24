"""API routes — workflow engine (playbook execution, status, approvals)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from magenta.core.mission import mission_manager
from magenta.core.models import Playbook, PlaybookV2
from magenta.core.playbook import playbook_manager
from magenta.exceptions import PlaybookError
from magenta.workflows.compiler import workflow_compiler
from magenta.workflows.engine import workflow_engine

router = APIRouter()

# Workflow execution roles — extend as needed
_ALLOWED_EXECUTION_ROLES = {"admin", "operator"}
_ALLOWED_APPROVAL_ROLES = {"admin", "operator", "approver"}
_ALLOWED_READ_ROLES = {"admin", "operator", "viewer"}


async def require_roles(request: Request, required_roles: set[str]) -> str:
    """Dependency: check if user has any of the required roles from JWT token."""
    # First check X-Magenta-Role header (for backward compatibility / mock auth)
    x_magenta_role = request.headers.get("X-Magenta-Role", "")
    if x_magenta_role:
        role = x_magenta_role.lower()
        if role not in required_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{x_magenta_role}' not authorized",
            )
        return role

    # Then check JWT token roles from auth middleware
    token_roles = getattr(request.state, "token_roles", [])
    if token_roles:
        for role in token_roles:
            if role in required_roles:
                return role
        raise HTTPException(
            status_code=403,
            detail=f"Required roles: {required_roles}, found: {token_roles}",
        )

    # No roles found
    raise HTTPException(
        status_code=403,
        detail="Authentication required: missing roles",
    )


async def require_execution_role(request: Request) -> str:
    """Dependency: require operator/admin role for workflow execution."""
    return await require_roles(request, _ALLOWED_EXECUTION_ROLES)


async def require_approval_role(request: Request) -> str:
    """Dependency: require approver/operator/admin role for approval actions."""
    return await require_roles(request, _ALLOWED_APPROVAL_ROLES)


async def require_read_role(request: Request) -> str:
    """Dependency: require viewer/operator/admin role for read access."""
    return await require_roles(request, _ALLOWED_READ_ROLES)


# ── Playbook management ───────────────────────────────────────────────

@router.get("/playbooks")
async def list_playbooks(
    tag: str | None = Query(None),
    role: str = Depends(require_read_role),
):
    """List registered playbooks."""
    playbooks = playbook_manager.list(tag=tag)
    return [
        {
            "name": p.name,
            "version": p.version,
            "tags": p.tags,
            "stages": len(p.stages),
            "updated_at": p.updated_at.isoformat(),
        }
        for p in playbooks
    ]


@router.post("/playbooks/validate")
async def validate_playbook(
    data: dict,
    role: str = Depends(require_read_role),
):
    """Validate a playbook YAML/JSON structure.

    Accepts either v1 (legacy) or v2 (magenta.soar/v1) format.
    Returns validation errors or success with node count.
    """
    try:
        if data.get("apiVersion", "").startswith("magenta.soar"):
            playbook = PlaybookV2(**data)
        else:
            playbook = Playbook(**data)

        nodes = workflow_compiler.compile(playbook)
        return {
            "valid": True,
            "node_count": len(nodes),
            "nodes": [
                {"id": nid, "role": n.role, "depends_on": n.depends_on}
                for nid, n in nodes.items()
            ],
        }
    except PlaybookError as exc:
        return {"valid": False, "errors": [str(exc)]}
    except Exception as exc:
        return {"valid": False, "errors": [f"Validation error: {exc}"]}


@router.post("/playbooks/register")
async def register_playbook(
    data: dict,
    role: str = Depends(require_execution_role),
):
    """Register a playbook in the in-memory registry."""
    try:
        pb = Playbook(**data)
        playbook_manager.register(pb)
        return {"status": "registered", "name": pb.name, "version": pb.version}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Workflow execution ────────────────────────────────────────────────

@router.post("/execute")
async def execute_workflow(
    request: dict = Body(...),
    role: str = Depends(require_execution_role),
):
    """Execute a playbook as a workflow.

    Request body:
      - playbook_path: str (file path to YAML/JSON playbook) OR
      - playbook: dict (inline playbook definition)
      - alert_id: str
      - source_system: str
      - description: str (optional)
      - parameters: dict (optional, overrides playbook parameters)

    Returns mission_id for tracking.
    """
    alert_id = request.get("alert_id")
    source_system = request.get("source_system", "sentinel")
    description = request.get("description", "")
    parameters = request.get("parameters")

    playbook_path = request.get("playbook_path")
    playbook_data = request.get("playbook")

    if not alert_id:
        raise HTTPException(status_code=400, detail="alert_id is required")

    try:
        if playbook_path:
            mission_id = await workflow_engine.execute_playbook(
                playbook=Path(playbook_path),
                alert_id=alert_id,
                source_system=source_system,
                description=description,
                parameters=parameters,
            )
        elif playbook_data:
            if playbook_data.get("apiVersion", "").startswith("magenta.soar"):
                pb = PlaybookV2(**playbook_data)
            else:
                pb = Playbook(**playbook_data)

            mission = mission_manager.create(
                alert_id=alert_id,
                source_system=source_system,
                playbook=pb if isinstance(pb, Playbook) else pb.to_legacy(),
                description=description,
            )
            if parameters:
                mission.artifact_bundle.update({"workflow_parameters": parameters})

            from magenta.workflows.engine import WorkflowExecution
            name = pb.metadata.get("name", "") if isinstance(pb, PlaybookV2) else pb.name
            execution = WorkflowExecution(
                mission_id=mission.mission_id,
                playbook_name=name,
            )
            workflow_engine._executions[mission.mission_id] = execution

            import asyncio
            asyncio.create_task(workflow_engine._run_workflow(mission.mission_id, pb))

            mission_id = mission.mission_id
        else:
            raise HTTPException(status_code=400, detail="playbook_path or playbook is required")

        return {
            "mission_id": mission_id,
            "status": "accepted",
            "message": "Workflow execution started",
        }
    except PlaybookError as exc:
        raise HTTPException(status_code=400, detail=f"Playbook error: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Execution error: {exc}")


# ── Execution status ──────────────────────────────────────────────────

@router.get("/{mission_id}/status")
async def get_workflow_status(
    mission_id: str,
    role: str = Depends(require_read_role),
):
    """Get workflow execution status."""
    execution = workflow_engine.get_execution_status(mission_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Workflow execution not found")

    return {
        "mission_id": mission_id,
        "playbook_name": execution.playbook_name,
        "status": execution.status,
        "current_node": execution.current_node,
        "started_at": execution.started_at.isoformat(),
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "approvals_pending": list(execution.approvals_pending.keys()),
    }


@router.get("/{mission_id}/nodes")
async def get_workflow_nodes(
    mission_id: str,
    role: str = Depends(require_read_role),
):
    """Get per-node execution results for a workflow."""
    execution = workflow_engine.get_execution_status(mission_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Workflow execution not found")

    nodes = []
    for node_id, result in execution.node_results.items():
        nodes.append({"id": node_id, "status": "completed", "result": result})
    for node_id, error in execution.node_errors.items():
        nodes.append({"id": node_id, "status": "failed", "error": error})

    return {"mission_id": mission_id, "nodes": nodes}


# ── Approval gate ─────────────────────────────────────────────────────

@router.post("/{mission_id}/approve/{approval_id}")
async def respond_to_approval(
    mission_id: str,
    approval_id: str,
    decision: str = Query(..., description="approved or denied"),
    approver_id: str = Query("operator"),
    reason: str = Query(""),
    role: str = Depends(require_approval_role),
):
    """Respond to a workflow approval gate."""
    from datetime import datetime

    if decision not in ("approved", "denied"):
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'denied'")

    success = await workflow_engine.respond_to_approval(approval_id, decision)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Approval request not found or already resolved",
        )

    try:
        from magenta.response.executor import approval_gate
        if decision == "approved":
            await approval_gate.approve(approval_id, approver_id, reason)
        else:
            await approval_gate.reject(approval_id, reason)
    except Exception:
        pass

    return {
        "status": decision,
        "approval_id": approval_id,
        "approver": approver_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Subgraph info ─────────────────────────────────────────────────────

@router.get("/subgraphs/list")
async def list_subgraphs(role: str = Depends(require_read_role)):
    """List available LangGraph subgraphs."""
    from magenta.workflows.langgraph.engine import HAS_LANGGRAPH, list_subgraphs
    if not HAS_LANGGRAPH:
        return {"subgraphs": [], "note": "LangGraph not available"}
    return {"subgraphs": list_subgraphs()}


# ── MCP tools info ────────────────────────────────────────────────────

@router.get("/tools/list")
async def list_workflow_tools(role: str = Depends(require_read_role)):
    """List MCP tools available to workflow subgraphs."""
    from magenta.workflows.mcp.tool_registry import HAS_LANGCHAIN, list_tools
    if not HAS_LANGCHAIN:
        return {"tools": [], "note": "LangChain not available"}
    return {"tools": list_tools()}
