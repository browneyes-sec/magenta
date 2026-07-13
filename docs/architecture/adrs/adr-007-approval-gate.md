# ADR-007: Approval Gate Architecture

## Status
Accepted

## Context
The DTP specifies that high-risk actions (risk_score > 70) require human approval before SOAR dispatch. The `ApprovalRequest` model was fully defined in `models.py` but there was no implementation that:
1. Persisted the approval request
2. Exposed the approval queue via REST API
3. Fed the approval decision back to the orchestrator

## Decision
Implement a three-layer approval gate:
1. **ApprovalStore** (`magenta/core/approval_store.py`) — manages request lifecycle (pending → approved/denied/expired)
2. **Approval API** (`magenta/api/routes/approvals.py`) — REST endpoints for GET queue, POST approve/deny
3. **EventHub notification** — approval decisions published to `approval-responses` topic for orchestrator wake-up

The approval gate is triggered when `routing-rules.yaml` `risk_score_threshold` is exceeded. The `SOARDispatcher` checks routing rules before dispatching; if approval is required, it creates an `ApprovalRequest` and blocks SOAR dispatch until the decision arrives.

## Rationale
- **Separation of concerns**: store, API, and notification are separate concerns
- **Asynchronous notification**: the orchestrator is not polling — EventHub wakes it on decision
- **15-minute TTL**: requests expire automatically, preventing stalled missions
- **Risk-score sorted queue**: analysts see highest-risk actions first

## Consequences
- Positive: Human-in-the-loop for high-risk actions as required by `llm-policy.md`
- Positive: Approval decisions are audited in the registry
- Negative: Blocked missions require human attention within the TTL window
- Negative: EventHub notification is best-effort; orchestrator must also poll for pending approvals on startup

## Compliance
- Risk score > threshold must create an approval request before SOAR dispatch
- Approval decisions must be logged as `automation.activity`
- Expired requests must be treated as denied (fail-closed for security)
