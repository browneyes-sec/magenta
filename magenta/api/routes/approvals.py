"""API routes — approval gate management."""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

from magenta.response.executor import approval_gate

router = APIRouter()


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
