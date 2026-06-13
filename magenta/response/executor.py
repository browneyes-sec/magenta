"""Response execution — action executor, approval gate."""

from typing import Any, Optional, Callable
from datetime import datetime
from uuid import uuid4

from magenta.core.models import (
    ActionType, ActionStatus, ApprovalState, ApprovalRequest, Target, TargetType
)
from magenta.exceptions import ApprovalError


class ActionExecutor:
    """Executes response actions with idempotency and approval gating."""

    def __init__(self):
        self._approval_callbacks: list[Callable] = []

    async def execute(
        self,
        action: ActionType,
        target: Target,
        params: dict[str, Any],
        skip_approval: bool = False,
    ) -> dict[str, Any]:
        """Execute an action, checking approval gate first."""
        from magenta.orchestration.state import state_store

        # Idempotency check
        idempotency_key = f"{action.value}:{target.id}"
        if await state_store.exists(f"idempotency:{idempotency_key}"):
            return {"status": "duplicate", "action": action.value, "target": target.id}

        # Approval gate
        risk_score = self._calculate_risk(action, target)
        if risk_score > 60 and not skip_approval:
            approval = await self._request_approval(
                action=action,
                target=target,
                risk_score=risk_score,
            )
            if approval.state in (ApprovalState.denied, ApprovalState.pending):
                return {
                    "status": "pending_approval",
                    "approval_id": approval.correlation_id,
                    "action": action.value,
                    "risk_score": risk_score,
                }

        # Execute
        await state_store.set(
            f"idempotency:{idempotency_key}",
            {"executed_at": datetime.utcnow().isoformat()},
            ttl_seconds=86400,
        )

        return {
            "status": "executed",
            "action": action.value,
            "target": target.id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _request_approval(
        self,
        action: ActionType,
        target: Target,
        risk_score: int,
    ) -> ApprovalRequest:
        """Request human approval for a high-risk action."""
        from datetime import timedelta

        request = ApprovalRequest(
            correlation_id=str(uuid4()),
            agent_id="executor",
            action=action,
            target=target,
            risk_score=risk_score,
            reasoning=f"Risk score {risk_score} exceeds threshold of 60",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        )

        for cb in self._approval_callbacks:
            await cb(request)

        return request

    def on_approval_request(self, callback: Callable) -> None:
        """Register callback for approval requests."""
        self._approval_callbacks.append(callback)

    def _calculate_risk(self, action: ActionType, target: Target) -> int:
        """Calculate risk score for an action."""
        risk_map = {
            ActionType.disable_account: 60,
            ActionType.isolate_host: 80,
            ActionType.block_ip: 50,
            ActionType.block_url: 30,
            ActionType.reset_password: 40,
            ActionType.enable_mfa: 20,
            ActionType.create_ticket: 5,
            ActionType.notify_user: 5,
        }

        base_risk = risk_map.get(action, 30)
        criticality_modifier = {
            "critical": 20, "high": 10, "medium": 0, "low": -10,
        }
        mod = criticality_modifier.get(
            target.asset_criticality.value if target.asset_criticality else "medium", 0
        )

        return max(0, min(100, base_risk + mod))


class ApprovalGate:
    """Manages the approval lifecycle."""

    def __init__(self):
        self._approvals: dict[str, ApprovalRequest] = {}

    async def approve(self, approval_id: str, approver_id: str, comment: str = "") -> dict:
        """Approve a pending action."""
        request = self._approvals.get(approval_id)
        if not request:
            raise ApprovalError(f"Approval {approval_id} not found")

        if datetime.utcnow() > request.expires_at:
            raise ApprovalError(f"Approval {approval_id} has expired")

        return {
            "status": "approved",
            "approval_id": approval_id,
            "approver": approver_id,
            "action": request.action.value,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def reject(self, approval_id: str, reason: str = "") -> dict:
        """Reject a pending action."""
        request = self._approvals.get(approval_id)
        if not request:
            raise ApprovalError(f"Approval {approval_id} not found")

        return {
            "status": "rejected",
            "approval_id": approval_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def list_pending(self) -> list[dict]:
        """List pending approvals."""
        return [
            {
                "id": cid,
                "action": req.action.value,
                "target": req.target.id,
                "risk_score": req.risk_score,
                "expires_at": req.expires_at.isoformat(),
            }
            for cid, req in self._approvals.items()
            if req.expires_at > datetime.utcnow()
        ]


action_executor = ActionExecutor()
approval_gate = ApprovalGate()
