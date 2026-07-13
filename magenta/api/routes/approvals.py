"""API routes — Approval Queue management.

Endpoints:
    GET    /approvals          — List pending approval requests
    GET    /approvals/{id}     — Get a single approval request
    POST   /approvals/{id}/approve — Approve an action
    POST   /approvals/{id}/deny    — Deny an action
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from magenta.core.approval_store import approval_store
from magenta.core.models import ApprovalState
from magenta.exceptions import ApprovalError

router = APIRouter(prefix="/approvals", tags=["Approvals"])


# ─── Request/Response Schemas ────────────────────────────────────────────


class ApprovalDecision(BaseModel):
    """Payload for approve/deny decisions."""

    action: str = Field(..., description="'approve' or 'deny'")
    approver_id: str = Field(..., description="Identity of the approving actor")
    comment: str = Field("", description="Optional rationale for the decision")


class ApprovalResponse(BaseModel):
    """Read model for approval requests in API responses."""

    correlation_id: str
    agent_id: str
    action_type: str
    target: str
    risk_score: int
    reasoning: str
    state: str
    model: str
    created_at: str
    expires_at: str
    is_expired: bool = False


# ─── Endpoints ───────────────────────────────────────────────────────────


@router.get("")
async def get_pending_approvals(
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    skip: int = Query(0, ge=0, description="Results to skip"),
) -> dict:
    """Get the pending approval queue, sorted by risk_score descending."""
    pending = await approval_store.get_pending(limit=limit, skip=skip)

    return {
        "total": len(pending),
        "limit": limit,
        "skip": skip,
        "approvals": [_format_request(req) for req in pending],
    }


@router.get("/{correlation_id}")
async def get_approval(correlation_id: str) -> dict:
    """Get a single approval request by correlation_id."""
    req = await approval_store.get(correlation_id)
    if not req:
        raise HTTPException(
            status_code=404,
            detail=f"Approval request {correlation_id} not found",
        )
    return _format_request(req)


@router.post("/{correlation_id}/approve")
async def approve_action(
    correlation_id: str,
    decision: ApprovalDecision,
) -> dict:
    """Approve a pending action — resumes the blocked mission."""
    try:
        await approval_store.update(
            correlation_id,
            ApprovalState.approved,
            decision.approver_id,
        )
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Notify orchestrator via EventHub (non-blocking)
    import asyncio

    asyncio.ensure_future(_notify_orchestrator(correlation_id, "approved", decision))

    return {
        "status": "approved",
        "correlation_id": correlation_id,
        "approver_id": decision.approver_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/{correlation_id}/deny")
async def deny_action(
    correlation_id: str,
    decision: ApprovalDecision,
) -> dict:
    """Deny a pending action — terminates the blocked mission."""
    try:
        await approval_store.update(
            correlation_id,
            ApprovalState.denied,
            decision.approver_id,
        )
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Notify orchestrator via EventHub (non-blocking)
    import asyncio

    asyncio.ensure_future(_notify_orchestrator(correlation_id, "denied", decision))

    return {
        "status": "denied",
        "correlation_id": correlation_id,
        "approver_id": decision.approver_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─── Helpers ─────────────────────────────────────────────────────────────


def _format_request(req) -> dict:
    """Format an ApprovalRequest for API response."""
    now = datetime.utcnow()
    is_expired = req.expires_at and now > req.expires_at
    return {
        "correlation_id": req.correlation_id,
        "agent_id": req.agent_id,
        "action_type": req.action.value if hasattr(req.action, "value") else str(req.action),
        "target": str(req.target.id) if hasattr(req.target, "id") else str(req.target),
        "risk_score": req.risk_score,
        "reasoning": req.reasoning,
        "state": req.state.value if hasattr(req.state, "value") else str(req.state),
        "model": req.model,
        "created_at": req.expires_at.isoformat() if hasattr(req, "expires_at") else "",
        "expires_at": req.expires_at.isoformat() if hasattr(req, "expires_at") else "",
        "is_expired": is_expired,
    }


async def _notify_orchestrator(
    correlation_id: str,
    action: str,
    decision: ApprovalDecision,
) -> None:
    """Send approval decision to orchestrator via EventHub."""
    try:
        from magenta.integration.eventhub import EventHubClient

        client = EventHubClient()
        await client.send(
            "approval-responses",
            {
                "correlation_id": correlation_id,
                "action": action,
                "approver_id": decision.approver_id,
                "comment": decision.comment,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    except Exception as e:
        # Approval decisions are durable in the store; EventHub notification
        # is best-effort for orchestrator wake-up
        import logging

        logging.getLogger(__name__).warning(
            "Failed to notify orchestrator of approval %s: %s",
            correlation_id[:8],
            e,
        )
