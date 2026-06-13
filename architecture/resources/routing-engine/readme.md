# Routing Engine Architecture

## Component Overview

The Orchestrator Agent applies routing rules and risk policy to enriched alerts, determining the appropriate response path: auto-resolve, dispatch to SOAR playbook, trigger Logic App, or queue for human approval.

DTP reference: §2.2 (Orchestrator Agent), §7.2, §11

## Decision Flow

```
enriched-alerts (canonical event)
    │
    ▼
┌─────────────────────────────────────┐
│        Orchestrator Agent           │
│                                     │
│  1. Load routing rules (YAML)       │
│  2. Match against alert attributes  │
│  3. Calculate risk score            │
│  4. Apply approval gate             │
│  5. Route to execution target       │
│  6. Publish action to 'actions'     │
└─────────────────────────────────────┘
    │
    ├──► SOAR Playbook (Splunk SOAR)
    ├──► Logic App (Azure native)
    ├──► Azure Function (custom action)
    ├──► Auto-resolve (no action needed)
    └──► Approval Gate (human review)
```

## Routing Rules (YAML)

Rules are version-controlled in Git and evaluated in priority order. First match wins.

```yaml
# config/routing-rules.yaml
routing_rules:
  - name: "ransomware-critical"
    priority: 100
    match:
      mitre_tactics: ["TA0040"]  # Impact
      severity: { gte: 4 }       # High or Critical
      blast_radius: ["domain", "enterprise"]
    action:
      type: "soar_playbook"
      playbook: "ransomware-response"
      params:
        isolate_automatically: true
        notify_soc_manager: true

  - name: "identity-compromise"
    priority: 90
    match:
      action: ["disable_account", "reset_password"]
      target.type: "user"
      target.asset_criticality: ["critical", "high"]
    action:
      type: "soar_playbook"
      playbook: "identity-compromise-triage"
    approval:
      required: true
      risk_threshold: 50

  - name: "phishing-low-confidence"
    priority: 50
    match:
      mitre_tactics: ["TA0001"]  # Initial Access
      tags: { has: "phishing" }
      confidence: { lt: 0.6 }
    action:
      type: "approval_gate"
      routing: "debate"
      agents_required: 3
      consensus_threshold: 0.7

  - name: "auto-resolve-low-severity"
    priority: 10
    match:
      severity: { lte: 2 }
      confidence: { gte: 0.9 }
    action:
      type: "auto_resolve"
      reason: "Low severity, high confidence — no action needed"
```

## Risk Score Formula

From DTP §7.2:

```python
def calculate_risk_score(alert: dict) -> int:
    """
    risk_score = asset_criticality × severity × blast_radius

    asset_criticality: critical=40, high=30, medium=20, low=10
    severity:          5=50, 4=40, 3=20, 2=10, 1=5
    blast_radius:      enterprise=3.0, domain=2.0, subnet=1.5, single-user=1.0
    """
    criticality_map = {"critical": 40, "high": 30, "medium": 20, "low": 10}
    severity_map = {5: 50, 4: 40, 3: 20, 2: 10, 1: 5}
    blast_map = {"enterprise": 3.0, "domain": 2.0, "subnet": 1.5, "single-user": 1.0}

    criticality = criticality_map.get(alert.get("target", {}).get("asset_criticality", "low"), 10)
    severity = severity_map.get(alert.get("severity", 2), 10)
    blast = blast_map.get(alert.get("blast_radius", "single-user"), 1.0)

    score = criticality * severity / 100 * blast
    return min(int(score), 100)
```

### Score Interpretation

| Range | Level | Routing |
|---|---|---|
| 0-30 | Low | Auto-resolve or direct SOAR |
| 31-50 | Moderate | SOAR playbook, optional approval |
| 51-70 | Elevated | SOAR playbook with approval |
| 71-85 | High | Human lead — agents advise |
| 86-100 | Critical | Emergency — execute immediately, notify SOC |

## Approval Gate

```python
class ApprovalGate:
    async def evaluate(self, alert: dict, risk_score: int) -> ApprovalDecision:
        if risk_score >= 86:
            return ApprovalDecision(action="execute_immediately", notify_soc=True)
        elif risk_score >= 71:
            return ApprovalDecision(action="human_lead", escalate=True)
        elif risk_score >= 51:
            return ApprovalDecision(action="request_approval", tier="analyst")
        elif risk_score >= 31:
            # Check if rule requires approval
            rule = self._find_matching_rule(alert)
            if rule and rule.get("approval", {}).get("required"):
                return ApprovalDecision(action="request_approval", tier="analyst")
            return ApprovalDecision(action="execute")
        else:
            return ApprovalDecision(action="execute")
```

## Execution Targets

| Target | Type | When |
|---|---|---|
| Splunk SOAR | SOAR playbook | Complex multi-step playbooks |
| Azure Logic App | Managed connector | Direct Azure actions (disable AD account, isolate via Defender) |
| Azure Function | Python function | Custom actions not covered by connectors |
| Auto-resolve | None | Low-risk, high-confidence alerts |
| Human | Escalation | High-risk actions requiring judgment |

## Configuration

```yaml
orchestrator:
  risk_scoring:
    criticality_weights:
      critical: 40
      high: 30
      medium: 20
      low: 10
    severity_weights:
      5: 50
      4: 40
      3: 20
      2: 10
      1: 5
    blast_radius_multipliers:
      enterprise: 3.0
      domain: 2.0
      subnet: 1.5
      single-user: 1.0

  approval:
    tiers:
      analyst:
        timeout_seconds: 300
        auto_approve_on_timeout: false
      soc_manager:
        timeout_seconds: 600
        auto_approve_on_timeout: false
      emergency:
        notify_slack_channel: "#soc-critical"
        notify_pagerduty: true
```

## Monitoring

| Metric | Alert |
|---|---|
| No matching rule for alert > 10% | Warning — ruleset gap |
| Routing error rate > 2% | Warning |
| Approval queue depth > 20 | Warning |
| Risk score calculation failure > 0 | Investigate |
| Rule evaluation latency p99 > 200 ms | Warning |
