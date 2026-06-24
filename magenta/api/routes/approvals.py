"""API routes — approval gate management."""

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from magenta.core.models import (
    ActionType,
    ApprovalRequest,
    Target,
    TargetType,
)
from magenta.response.executor import DurableApprovalStore, approval_gate

router = APIRouter()

_approval_store = DurableApprovalStore()


async def create_approval_request(
    mission_id: str,
    action: str,
    target: dict,
    risk_score: int = 50,
    reasoning: str = "Workflow approval required",
    expires_minutes: int = 30,
) -> str:
    """Create an approval request for a workflow approval gate.

    Returns the approval_id (correlation_id).
    """
    approval_id = f"approval-{uuid4().hex[:8]}"

    if target.get("type"):
        target_type = TargetType(target["type"])
    else:
        target_type = TargetType.host
    target_obj = Target(type=target_type, id=target.get("id", "unknown"))

    try:
        action_type = ActionType(action)
    except ValueError:
        action_type = ActionType.custom

    request = ApprovalRequest(
        correlation_id=approval_id,
        agent_id=f"workflow-{mission_id}",
        action=action_type,
        target=target_obj,
        risk_score=risk_score,
        reasoning=reasoning,
        expires_at=datetime.utcnow() + timedelta(minutes=expires_minutes),
        model="workflow-engine",
    )

    await _approval_store.save(request)
    approval_gate._approvals[approval_id] = request

    return approval_id


@router.get("/pending")
async def list_pending_approvals():
    """List all pending approval requests."""
    return {"approvals": await approval_gate.list_pending()}


@router.get("/{approval_id}")
async def get_approval(approval_id: str):
    """Get details of a specific approval request."""
    request = approval_gate._approvals.get(approval_id)
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return {
        "correlation_id": request.correlation_id,
        "agent_id": request.agent_id,
        "action": request.action.value,
        "target": {"type": request.target.type.value, "id": request.target.id},
        "risk_score": request.risk_score,
        "reasoning": request.reasoning,
        "alternatives": request.alternatives,
        "evidence": request.evidence,
        "expires_at": request.expires_at.isoformat(),
        "model": request.model,
    }


@router.post("/{approval_id}/respond")
async def respond_to_approval(
    approval_id: str,
    decision: str = Query(..., description="approved or denied"),
    approver_id: str = Query("operator"),
    reason: str = Query(""),
):
    """Respond to an approval request (approve or deny)."""
    if decision not in ("approved", "denied"):
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'denied'")

    from magenta.exceptions import ApprovalError

    try:
        if decision == "approved":
            result = await approval_gate.approve(approval_id, approver_id, reason)
        else:
            result = await approval_gate.reject(approval_id, reason)
    except ApprovalError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return result
