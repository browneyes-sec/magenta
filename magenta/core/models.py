"""
Domain models for the Magenta ASOAR framework.

All models are Pydantic v2, matching the canonical `automation.activity`
schema defined in the DTP (§2.3).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from enum import Enum, StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class EventType(StrEnum):
    automation_activity = "automation.activity"


class SourceSystem(StrEnum):
    sentinel = "sentinel"
    splunk = "splunk"


class ActionType(StrEnum):
    disable_account = "disable_account"
    isolate_host = "isolate_host"
    create_ticket = "create_ticket"
    block_ip = "block_ip"
    block_url = "block_url"
    reset_password = "reset_password"
    enable_mfa = "enable_mfa"
    run_scan = "run_scan"
    collect_forensics = "collect_forensics"
    notify_user = "notify_user"
    escalate_ticket = "escalate_ticket"
    custom = "custom"


class ActionStatus(StrEnum):
    queued = "queued"
    executing = "executing"
    succeeded = "succeeded"
    failed = "failed"
    rejected = "rejected"
    pending_approval = "pending_approval"


class ApprovalState(StrEnum):
    pending = "pending"
    approved = "approved"
    denied = "denied"
    auto_approved = "auto-approved"
    modified = "modified"


class TargetType(StrEnum):
    user = "user"
    host = "host"
    ip = "ip"
    process = "process"
    url = "url"
    domain = "domain"
    application = "application"


class AssetCriticality(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class BlastRadius(StrEnum):
    single_user = "single-user"
    subnet = "subnet"
    domain = "domain"
    enterprise = "enterprise"


class MissionStatus(StrEnum):
    created = "created"
    scoped = "scoped"
    assigned = "assigned"
    executing = "executing"
    review = "review"
    completed = "completed"
    escalated = "escalated"
    failed = "failed"
    cancelled = "cancelled"


class AgentStatus(StrEnum):
    idle = "idle"
    ready = "ready"
    executing = "executing"
    waiting_input = "waiting_input"
    error = "error"
    done = "done"


class SeverityLevel(int, Enum):
    informational = 1
    low = 2
    medium = 3
    high = 4
    critical = 5


class ApprovalRequest(BaseModel):
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    action: ActionType
    target: Target
    risk_score: int = Field(ge=0, le=100)
    reasoning: str
    alternatives: list[dict] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    state: ApprovalState = ApprovalState.pending
    approval: dict | None = None
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=15))
    model: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None


class Target(BaseModel):
    type: TargetType
    id: str
    asset_criticality: AssetCriticality | None = None


class Executor(BaseModel):
    type: Literal["agent", "logic_app", "function"] = "agent"
    id: str
    managed_identity: str | None = None


class Evidence(BaseModel):
    input_hash: str | None = None
    raw_alert_ref: str | None = None
    output_ref: str | None = None


class AutomationActivity(BaseModel):
    """Canonical automation.activity event schema."""

    schema_version: str = "1.0"
    event_type: EventType = EventType.automation_activity
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    idempotency_key: str = ""
    source_system: SourceSystem
    source_workspace_id: str = ""
    source_alert_id: str = ""
    source_incident_id: str = ""
    playbook_id: str = ""
    playbook_run_id: str = ""
    action: ActionType
    target: Target
    status: ActionStatus = ActionStatus.queued
    approval: dict | None = None
    risk_score: int = 0
    blast_radius: BlastRadius = BlastRadius.single_user
    mitre_tactics: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    executor: Executor
    evidence: Evidence = Field(default_factory=Evidence)
    tags: list[str] = Field(default_factory=list)

    @field_validator("idempotency_key", mode="before")
    @classmethod
    def generate_idempotency_key(cls, v, info):
        if not v:
            data = info.data
            raw = f"{data.get('source_alert_id', '')}:{data.get('action', '')}:{data.get('target', Target(type='user', id='')).id}"
            return hashlib.sha256(raw.encode()).hexdigest()
        return v


class AgentConfig(BaseModel):
    agent_id: str
    role: str
    version: str = "1.0.0"
    model_provider: str = "ollama"
    model_name: str = "qwen2.5:7b"
    instructions: str = ""
    tools: list[str] = Field(default_factory=list)
    risk_tolerance: float = Field(default=0.6, ge=0.0, le=1.0)
    escalation_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    max_concurrent_tasks: int = 3
    max_turns: int = 10
    ollama_host: str = "http://localhost:11434"


class Mission(BaseModel):
    mission_id: str = Field(default_factory=lambda: str(uuid4()))
    status: MissionStatus = MissionStatus.created
    alert_id: str = ""
    source_system: SourceSystem = SourceSystem.sentinel
    playbook_id: str = ""
    playbook_version: str = ""
    severity: SeverityLevel = SeverityLevel.medium
    risk_score: int = 0
    description: str = ""
    team: list[AgentConfig] = Field(default_factory=list)
    tasks: list[dict] = Field(default_factory=list)
    artifact_bundle: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))


class Playbook(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0.0"
    trigger: dict = Field(default_factory=dict)
    orchestration: dict = Field(default_factory=dict)
    stages: list[dict] = Field(default_factory=list)
    governance: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WorkflowNodeType(StrEnum):
    ingest = "ingest"
    agentic = "agentic"
    decision = "decision"
    approval = "approval"
    action = "action"
    publisher = "publisher"
    parallel = "parallel"
    subgraph = "subgraph"


class WorkflowNode(BaseModel):
    id: str
    type: WorkflowNodeType
    label: str = ""
    agent: str | None = None
    subgraph: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    condition: str | None = None
    position: dict = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    source: str
    target: str
    condition: str | None = None
    label: str = ""


class WorkflowSpec(BaseModel):
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)


class SubgraphSpec(BaseModel):
    name: str
    description: str = ""
    entry_node: str
    nodes: list[dict] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    state_schema: dict = Field(default_factory=dict)


class GovernanceSpec(BaseModel):
    approval_required: list[dict] = Field(default_factory=list)
    audit: dict = Field(default_factory=dict)
    compliance_frameworks: list[str] = Field(default_factory=list)
    cost_limits: dict = Field(default_factory=dict)
    sla: dict = Field(default_factory=dict)


class PlaybookV2(BaseModel):
    apiVersion: str = Field(default="magenta.soar/v1", alias="apiVersion")  # noqa: N815
    kind: str = "Playbook"
    metadata: dict = Field(default_factory=dict)
    spec: dict = Field(default_factory=dict)

    @classmethod
    def from_legacy(cls, legacy: Playbook) -> PlaybookV2:
        return cls(
            apiVersion="magenta.soar/v1",
            kind="Playbook",
            metadata={
                "name": legacy.name,
                "version": legacy.version,
                "description": legacy.description,
                "tags": legacy.tags,
                "created": legacy.created_at.isoformat(),
                "updated": legacy.updated_at.isoformat(),
            },
            spec={
                "trigger": legacy.trigger,
                "orchestration": legacy.orchestration,
                "stages": legacy.stages,
                "governance": legacy.governance,
            },
        )

    def to_legacy(self) -> Playbook:
        return Playbook(
            name=self.metadata.get("name", ""),
            version=self.metadata.get("version", "1.0.0"),
            description=self.metadata.get("description", ""),
            trigger=self.spec.get("trigger", {}),
            orchestration=self.spec.get("orchestration", {}),
            stages=self.spec.get("stages", []),
            governance=self.spec.get("governance", {}),
            tags=self.metadata.get("tags", []),
        )


class HealthStatus(BaseModel):
    status: Literal["healthy", "degraded", "down"] = "healthy"
    checks: dict[str, ComponentHealth] = Field(default_factory=dict)
    uptime_seconds: float = 0.0


class ComponentHealth(BaseModel):
    status: Literal["healthy", "degraded", "down"]
    latency_ms: float = 0.0
    error_rate: float = 0.0
    message: str = ""
    last_check: datetime = Field(default_factory=datetime.utcnow)
