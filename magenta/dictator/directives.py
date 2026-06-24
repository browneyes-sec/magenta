"""Dictator directives — imperative commands issued to agents, probes, or subsystems."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class DirectiveType(str, Enum):
    deploy_agent = "deploy_agent"
    recall_agent = "recall_agent"
    override_teaming = "override_teaming"
    promote_probe = "promote_probe"
    inject_probe = "inject_probe"
    halt_mission = "halt_mission"
    resume_mission = "resume_mission"
    reassign_task = "reassign_task"
    escalate = "escalate"
    policy_override = "policy_override"
    system_command = "system_command"


class DirectivePriority(str, Enum):
    critical = "critical"
    high = "high"
    normal = "normal"
    low = "low"


class Directive(BaseModel):
    """An imperative directive issued by the Dictator."""

    directive_id: str = Field(default_factory=lambda: str(uuid4()))
    type: DirectiveType
    priority: DirectivePriority = DirectivePriority.normal
    target: str
    mission_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    executed: bool = False
    result: dict | None = None

    def dict(self) -> dict:
        return self.model_dump()


def issue_directive(
    dtype: DirectiveType,
    target: str,
    mission_id: str | None = None,
    payload: dict | None = None,
    reason: str = "",
    priority: DirectivePriority = DirectivePriority.normal,
) -> Directive:
    """Create and log a new directive through the Dictator state.

    Emits OTel span and writes to Elasticsearch (best-effort).
    """
    from magenta.dictator.state import dictator_state

    directive = Directive(
        type=dtype,
        priority=priority,
        target=target,
        mission_id=mission_id,
        payload=payload or {},
        reason=reason,
    )
    dictator_state.log_directive(directive.dict())

    # Telemetry — best-effort, non-blocking
    from magenta.dictator.telemetry import emit_directive_span
    emit_directive_span(directive.dict())

    try:
        import asyncio

        from magenta.dictator.telemetry import write_directive_to_elastic
        asyncio.ensure_future(write_directive_to_elastic(directive.dict()))
    except Exception:
        pass

    return directive
