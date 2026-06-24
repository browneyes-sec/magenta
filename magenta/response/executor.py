"""Response execution — action executor, approval gate with Redis persistence."""

import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from magenta.core.models import ActionType, ApprovalRequest, ApprovalState, Target
from magenta.exceptions import ApprovalError
from magenta.orchestration.state import InMemoryStateStore

logger = logging.getLogger(__name__)


class DurableApprovalStore:
    """Redis-backed persistence for approval requests.

    Owns its Redis connection. Falls back to in-memory if Redis is unavailable.
    """

    def __init__(self, redis_url: str = ""):
        self._redis_url = redis_url or "redis://localhost:6379/0"
        self._redis = None
        self._in_memory: dict[str, ApprovalRequest] = {}

    async def _ensure_redis(self) -> Any:
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(self._redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
        except Exception:
            self._redis = False
        return self._redis

    async def save(self, request: ApprovalRequest, ttl: int = 900) -> None:
        key = f"approval:{request.correlation_id}"
        self._in_memory[request.correlation_id] = request
        client = await self._ensure_redis()
        if client:
            try:
                await client.setex(key, ttl, request.model_dump_json())
            except Exception as exc:
                logger.debug("Redis save failed for %s: %s", key, exc)

    async def remove(self, approval_id: str) -> None:
        self._in_memory.pop(approval_id, None)
        client = await self._ensure_redis()
        if client:
            try:
                await client.delete(f"approval:{approval_id}")
            except Exception:
                pass

    async def load_all(self) -> dict[str, ApprovalRequest]:
        now = datetime.utcnow()
        client = await self._ensure_redis()
        if client:
            try:
                keys = await client.keys("approval:*")
                for key in keys:
                    name = key.split(":", 1)[1]
                    if name in self._in_memory:
                        continue
                    data = await client.get(key)
                    if data:
                        parsed = json.loads(data)
                        expires = datetime.fromisoformat(
                            parsed["expires_at"].replace("Z", "+00:00")[:19]
                        )
                        if expires > now:
                            self._in_memory[name] = ApprovalRequest(
                                correlation_id=parsed["correlation_id"],
                                agent_id=parsed["agent_id"],
                                action=ActionType(parsed["action"]),
                                target=Target(**parsed["target"]),
                                risk_score=parsed["risk_score"],
                                reasoning=parsed["reasoning"],
                                expires_at=expires,
                                model=parsed.get("model", ""),
                            )
            except Exception:
                pass
        return self._in_memory

    def get(self, approval_id: str) -> ApprovalRequest | None:
        return self._in_memory.get(approval_id)


class ActionExecutor:
    """Executes response actions with idempotency and approval gating."""

    def __init__(self, approval_store: DurableApprovalStore | None = None):
        self._approval_callbacks: list[Callable] = []
        self._approval_store = approval_store or DurableApprovalStore()

    async def execute(
        self,
        action: ActionType,
        target: Target,
        params: dict[str, Any],
        skip_approval: bool = False,
    ) -> dict[str, Any]:
        """Execute an action, checking approval gate first."""
        from magenta.orchestration.state import state_store

        # Idempotency check using SETNX atomicity
        idempotency_key = f"idempotency:{action.value}:{target.id}"
        if isinstance(state_store, InMemoryStateStore):
            if await state_store.exists(idempotency_key):
                return {"status": "duplicate", "action": action.value, "target": target.id}
        else:
            set_ok = await state_store.setnx(
                idempotency_key,
                {"executed_at": datetime.utcnow().isoformat()},
                ttl_seconds=86400,
            )
            if not set_ok:
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

        # Execute (mark idempotency for in-memory store)
        if isinstance(state_store, InMemoryStateStore):
            await state_store.set(
                idempotency_key,
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
        request = ApprovalRequest(
            correlation_id=str(uuid4()),
            agent_id="executor",
            action=action,
            target=target,
            risk_score=risk_score,
            reasoning=f"Risk score {risk_score} exceeds threshold of 60",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        )

        await self._approval_store.save(request)

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
    """Manages the approval lifecycle with Redis persistence."""

    def __init__(self, approval_store: DurableApprovalStore | None = None):
        self._store = approval_store or DurableApprovalStore()
        self._approvals: dict[str, ApprovalRequest] = {}

    async def _refresh(self) -> None:
        self._approvals = await self._store.load_all()

    async def approve(self, approval_id: str, approver_id: str, comment: str = "") -> dict:
        """Approve a pending action."""
        await self._refresh()
        request = self._approvals.get(approval_id)
        if not request:
            raise ApprovalError(f"Approval {approval_id} not found")

        if datetime.utcnow() > request.expires_at:
            raise ApprovalError(f"Approval {approval_id} has expired")

        await self._store.remove(approval_id)

        return {
            "status": "approved",
            "approval_id": approval_id,
            "approver": approver_id,
            "action": request.action.value,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def reject(self, approval_id: str, reason: str = "") -> dict:
        """Reject a pending action."""
        await self._refresh()
        request = self._approvals.get(approval_id)
        if not request:
            raise ApprovalError(f"Approval {approval_id} not found")

        await self._store.remove(approval_id)

        return {
            "status": "rejected",
            "approval_id": approval_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def list_pending(self) -> list[dict]:
        """List pending approvals."""
        await self._refresh()

        return [
            {
                "id": cid,
                "action": req.action.value,
                "target": req.target.id,
                "risk_score": req.risk_score,
                "reasoning": req.reasoning[:80],
                "expires_at": req.expires_at.isoformat(),
            }
            for cid, req in self._approvals.items()
            if req.expires_at > datetime.utcnow()
        ]


action_executor = ActionExecutor()
approval_gate = ApprovalGate()
