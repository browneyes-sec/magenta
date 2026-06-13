# Approval Gate Architecture

## Component Overview

The Approval Gate enforces human-in-the-loop control over high-risk automated actions. It sits between the Orchestrator Agent's routing decision and actual execution, ensuring every action meets risk policy before being carried out.

DTP references: §1.3 (Guiding Principles), §2.2 (Orchestrator Agent), §7.2, §9 (Risk Register)

## Escalation Tiers

From the risk score formula (see [Routing Engine](../routing-engine/readme.md)):

| Tier | Risk Score | Behavior | Human Touch |
|---|---|---|---|
| **Auto-resolve** | 0-30 | Execute immediately | None |
| **Auto-approve** | 31-50 | Execute, log for audit | Periodic sampling |
| **Agent review** | 51-70 | Request approval from SOC analyst | Required |
| **Human lead** | 71-85 | Escalate to SOC manager | Full human takeover |
| **Emergency** | 86-100 | Execute immediately, notify in parallel | Notified post-facto |

## Approval Gate State Machine

```
                  ┌──────────┐
                  │ Received │
                  └────┬─────┘
                       │
                  ┌────▼─────┐
                  │ Evaluate │ ← risk score, blast radius, action type
                  └────┬─────┘
                       │
            ┌──────────┼──────────┐
            ▼          ▼          ▼
      ┌─────────┐ ┌─────────┐ ┌─────────┐
      │ Execute │ │ Request │ │Escalate│
      │ (auto)  │ │Approval │ │(human) │
      └────┬────┘ └────┬────┘ └────┬────┘
           │           │           │
           │      ┌────▼────┐     │
           │      │Pending  │     │
           │      └────┬────┘     │
           │           │          │
           │    ┌──────┼──────┐   │
           │    ▼      ▼      ▼   │
           │ ┌────┐ ┌────┐ ┌────┐ │
           │ │Appr│ │Deny│ │Time│ │
           │ │ove │ │    │ │out │ │
           │ └─┬──┘ └──┬─┘ └──┬─┘ │
           │   │       │       │   │
           └───┼───────┘───────┼───┘
               ▼               ▼
          ┌────────┐    ┌──────────┐
          │Executed│    │ Rejected │
          └────────┘    └──────────┘
```

## Approval Request Format

```python
# From magenta/core/models.py — ApprovalRequest schema
class ApprovalRequest(BaseModel):
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    action: ActionType
    target: Target
    risk_score: int = Field(ge=0, le=100)
    reasoning: str
    alternatives: list[dict] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    expires_at: datetime
```

```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_id": "contain-01",
  "action": "isolate_host",
  "target": {"type": "host", "id": "FIN-PROD-347", "asset_criticality": "critical"},
  "risk_score": 72,
  "reasoning": "Ransomware indicator detected on endpoint with high confidence.",
  "alternatives": [
    {"action": "disable_network_interface", "risk_score": 45, "impact": "Partial isolation"},
    {"action": "create_ticket_for_review", "risk_score": 10, "impact": "No immediate action"}
  ],
  "evidence": [
    "Alert: sentinel-incident-8932",
    "IOC: 185.220.101.42 (known C2)",
    "Process: encrypt.exe spawned on endpoint"
  ],
  "expires_at": "2026-06-13T20:00:00Z"
}
```

## Approval Response

```python
class ApprovalResponse(BaseModel):
    correlation_id: str
    approved: bool
    approver_id: str
    approver_notes: str = ""
    modified_action: Optional[ActionType] = None
    modified_target: Optional[Target] = None
```

## Shadow Mode

Shadow mode executes the approval gate logic but **never blocks** execution. Used for validation during pilot phases (DTP §7.2):

```yaml
approval_gate:
  mode: shadow  # log only — never block
  # mode: enforcing  # production — block if not approved
```

In shadow mode, every decision is logged as if it were enforced:

```json
{
  "correlation_id": "...",
  "shadow": true,
  "would_block": true,
  "would_escalate": false,
  "risk_score": 65,
  "action": "isolate_host",
  "disposition": "would_request_approval"
}
```

## Notification Channels

| Tier | Channel | Target | Template |
|---|---|---|---|
| Agent review | In-app (WebSocket) | SOC analyst dashboard | `action {action} on {target} needs approval` |
| Agent review | Slack / Teams | `#soc-approvals` channel | Interactive approve/deny buttons |
| Human lead | PagerDuty | SOC manager on-call | Escalation alert with mission context |
| Emergency | Slack + PagerDuty | SOC team + manager | `EMERGENCY: {action} executed on {target}` |
| Timeout escalation | Slack | SOC manager | `Approval request {id} expired, escalating` |

## Timeout Handling

```yaml
approval_gate:
  timeout_policy:
    analyst:
      timeout_seconds: 300
      on_timeout: escalate_to_manager
    soc_manager:
      timeout_seconds: 600
      on_timeout: execute_with_warning
    emergency:
      execute_immediately: true
```

## Metrics

```python
class ApprovalMetrics:
    async def record_decision(self, request: ApprovalRequest, response: ApprovalResponse):
        await self._increment("approval.requests.total")
        if response.approved:
            await self._increment("approval.requests.approved")
        else:
            await self._increment("approval.requests.denied")

        latency = (datetime.utcnow() - request.created_at).total_seconds()
        await self._histogram("approval.response_time_seconds", latency)
```

## Monitoring

| Metric | Alert |
|---|---|
| Approval queue depth > 10 | Warning — SOC may be overwhelmed |
| Approval response time p99 > 10 min | Warning |
| Denial rate > 20% | Investigate — agents proposing bad actions |
| Timeout rate > 5% | Warning — analysts not keeping up |
| Shadow mode would_block rate | Report — calibration metric for risk thresholds |
| Emergency actions > 5/day | Review — possible over-classification |
