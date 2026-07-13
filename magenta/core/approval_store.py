"""Approval request store — manages approval lifecycle for high-risk actions.

Stores approval requests in-memory (backed by Azure Table Storage in production).
The ApprovalRequest model is defined in magenta/core/models.py.

Lifecycle:
    pending → approved → mission resumes
    pending → denied   → mission terminated
    pending → expired  → mission auto-fails (after 15 min TTL)
"""

from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta
import logging

from magenta.core.models import ApprovalRequest, ApprovalState
from magenta.exceptions import ApprovalError

logger = logging.getLogger(__name__)


class ApprovalStore:
    """
    Manages the approval request queue.

    In production, this should be backed by Azure Table Storage or Cosmos DB.
    The in-memory implementation is suitable for development and testing.
    """

    def __init__(self):
        self._requests: dict[str, ApprovalRequest] = {}

    async def create(self, request: ApprovalRequest) -> ApprovalRequest:
        """Create a new approval request in pending state."""
        if request.correlation_id in self._requests:
            raise ApprovalError(
                f"Approval request {request.correlation_id} already exists"
            )
        self._requests[request.correlation_id] = request
        logger.info(
            "ApprovalStore: created request %s (risk_score=%d, action=%s)",
            request.correlation_id[:8],
            request.risk_score,
            request.action.value,
        )
        return request

    async def get(self, correlation_id: str) -> Optional[ApprovalRequest]:
        """Get a single approval request by correlation_id."""
        req = self._requests.get(correlation_id)
        if req and self._is_expired(req):
            req.state = ApprovalState.denied
            return req
        return req

    async def get_pending(
        self,
        limit: int = 50,
        skip: int = 0,
        sort_by: str = "risk_score",
    ) -> list[ApprovalRequest]:
        """Get pending approval requests, sorted by risk_score descending."""
        pending = []
        expired_coros = []
        for req in self._requests.values():
            if req.state == ApprovalState.pending:
                if self._is_expired(req):
                    req.state = ApprovalState.denied
                else:
                    pending.append(req)

        # Sort by risk_score descending (highest risk first)
        pending.sort(key=lambda r: r.risk_score, reverse=True)
        return pending[skip : skip + limit]

    async def update(
        self,
        correlation_id: str,
        new_state: ApprovalState,
        approver_id: str,
    ) -> ApprovalRequest:
        """Update the state of an approval request.

        Args:
            correlation_id: The approval request identifier.
            new_state: Must be 'approved' or 'denied'.
            approver_id: Identity of the approving actor.

        Returns:
            The updated ApprovalRequest.

        Raises:
            ApprovalError: If request not found or state transition invalid.
        """
        req = self._requests.get(correlation_id)
        if not req:
            raise ApprovalError(f"Approval request {correlation_id} not found")

        if req.state != ApprovalState.pending:
            raise ApprovalError(
                f"Approval request {correlation_id} is already {req.state.value}"
            )

        if new_state not in (ApprovalState.approved, ApprovalState.denied):
            raise ApprovalError(f"Invalid state transition: {new_state}")

        req.state = new_state
        if req.approval is None:
            req.approval = {}
        req.approval["state"] = new_state.value
        req.approval["approver_id"] = approver_id
        req.approval["timestamp"] = datetime.utcnow().isoformat()

        logger.info(
            "ApprovalStore: %s request %s by %s",
            new_state.value,
            correlation_id[:8],
            approver_id,
        )
        return req

    async def delete_expired(self) -> int:
        """Remove expired requests from the store. Returns count removed."""
        expired = [
            cid
            for cid, req in self._requests.items()
            if self._is_expired(req)
        ]
        for cid in expired:
            del self._requests[cid]
        if expired:
            logger.info("ApprovalStore: purged %d expired requests", len(expired))
        return len(expired)

    def _is_expired(self, req: ApprovalRequest) -> bool:
        """Check if an approval request has exceeded its TTL."""
        return req.expires_at and datetime.utcnow() > req.expires_at

    async def count_pending(self) -> int:
        """Get the count of pending (non-expired) approval requests."""
        count = 0
        for req in self._requests.values():
            if req.state == ApprovalState.pending and not self._is_expired(req):
                count += 1
        return count


approval_store = ApprovalStore()
