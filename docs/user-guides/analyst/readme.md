# Analyst User Guide

## Audience

SOC analysts, incident responders, and security operators using Magenta for daily triage, investigation, and response.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Managing Missions](#managing-missions)
3. [Working with Agents](#working-with-agents)
4. [Approval Workflows](#approval-workflows)
5. [Investigation & Reporting](#investigation--reporting)
6. [Playbooks](#playbooks)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Mission Lifecycle

```
Alert arrives ──► Mission Created ──► Agents Assigned ──► Execution ──► Review ──► Completed
                                                    │                        │
                                                    └── Human approval ─────┘
                                                    (if risk > threshold)
```

### Common Tasks

```bash
# View current missions
magenta orchestrate list

# View detailed mission info
magenta orchestrate get <mission-id>

# View mission logs
magenta orchestrate logs <mission-id> --tail 200

# View pending approvals
magenta response approval list
```

## Managing Missions

### Viewing Active Missions

```bash
$ magenta orchestrate list --status executing --format json
[
  {
    "mission_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "executing",
    "alert_id": "sentinel-incident-8932",
    "severity": 4,
    "tasks": 3,
    "team_size": 3
  }
]
```

### Mission States

| State | Meaning | Analyst Action |
|---|---|---|
| `created` | Mission initialized | None — auto-transitions |
| `scoped` | Context gathered | None — auto-transitions |
| `assigned` | Agents assigned | None — auto-transitions |
| `executing` | Agents working | Monitor progress |
| `review` | Ready for human review | Approve/reject actions |
| `completed` | Mission finished | Review final report |
| `escalated` | Needs human lead | Take over manually |
| `failed` | Error during execution | Investigate and retry |
| `cancelled` | Stopped by operator | Document reason |

### Manually Creating a Mission

```bash
magenta orchestrate create \
    --alert-id manual-001 \
    --source generic \
    --description "Suspicious PowerShell execution on DC-01"
magenta orchestrate start <mission-id>
```

### Stopping a Mission

```bash
# Graceful stop — agent completes current task, then halts
magenta orchestrate stop <mission-id>
```

## Working with Agents

### Agent Roles

| Agent | Role | When It Acts |
|---|---|---|
| Triage | Assess severity, route alerts | First responder to every mission |
| Enrich | Gather context, threat intel, CMDB | After triage completes |
| Contain | Execute containment actions | After enrichment |
| Investigate | Deep forensic analysis | Parallel with containment |
| Compliance | Regulatory check | Before final report |
| Report | Incident summary | Last step before completion |

### Viewing Agent Status

```bash
$ magenta health agents
┌──────────────┬─────────────┬────────┬──────┐
│ Agent ID     │ Role        │ Status │ Load │
├──────────────┼─────────────┼────────┼──────┤
│ triage-01    │ triage      │ ready  │ 0    │
│ enrich-01    │ enrich      │ ready  │ 2    │
│ contain-01   │ contain     │ ready  │ 1    │
│ swarm-01     │ swarm_mana… │ ready  │ 1    │
└──────────────┴─────────────┴────────┴──────┘
```

## Approval Workflows

### Reviewing Pending Approvals

```bash
$ magenta response approval list
┌──────────────────────────────────────┬──────────┬──────┬──────────┐
│ Correlation ID                      │ Agent    │ Risk │ Action   │
├──────────────────────────────────────┼──────────┼──────┼──────────┤
│ 550e8400-e29b-41d4-a716-44665544000 │ contain… │ 72   │ isolat…  │
└──────────────────────────────────────┴──────────┴──────┴──────────┘
```

### Approving or Rejecting

```bash
# Review details before deciding
magenta response approval get <correlation-id>

# Approve
magenta response approval approve <correlation-id>

# Reject with reason
magenta response approval reject <correlation-id> \
    --reason "Manual investigation needed first"
```

### Escalation Tiers

| Tier | Risk Score | What Happens |
|---|---|---|
| Auto-resolve | 0-40 | Agent acts, no human needed |
| Agent review | 41-70 | Agent proposes, analyst approves |
| Human lead | 71-85 | Analyst takes over, agents advise |
| Emergency | 86-100 | Agents act immediately, notify in parallel |

## Investigation & Reporting

### Viewing Mission Artifacts

Each mission collects evidence into an `artifact_bundle`:

```json
{
  "raw_incident": { ... },
  "enrichment": {
    "threat_intel": [...],
    "affected_assets": [...]
  },
  "investigation": {
    "timeline": [...],
    "findings": {...},
    "mitre_mapping": {...}
  },
  "actions_taken": [...],
  "report": {
    "summary": "...",
    "recommendations": [...]
  }
}
```

### Final Report Structure

When compliance and reporting agents complete, the mission produces:

```json
{
  "mission_id": "...",
  "alert_id": "sentinel-incident-8932",
  "severity": 4,
  "risk_score": 65,
  "status": "completed",
  "timeline": {
    "created": "2026-06-13T14:00:00Z",
    "triaged": "2026-06-13T14:01:30Z",
    "enriched": "2026-06-13T14:03:00Z",
    "contained": "2026-06-13T14:05:00Z",
    "investigated": "2026-06-13T14:10:00Z",
    "completed": "2026-06-13T14:12:30Z"
  },
  "agents_involved": ["triage-01", "enrich-01", "contain-01", ...],
  "actions_taken": [
    {"action": "disable_account", "target": "jdoe", "status": "succeeded"}
  ],
  "compliance": {
    "status": "compliant",
    "frameworks_checked": ["SOC2", "PCI-DSS"]
  }
}
```

## Playbooks

Playbooks define mission orchestration patterns. Available via CLI:

```bash
# List registered playbooks
magenta automate playbook list

# View playbook details
magenta automate playbook get ransomware-response

# Validate a playbook
magenta automate playbook validate --file new-playbook.yaml
```

## Troubleshooting

### Common Issues

| Symptom | Likely Cause | Resolution |
|---|---|---|
| Mission stuck on `executing` | Agent timeout | `magenta orchestrate stop` and retry |
| Agent error | Model unavailable (OLLAMA down) | `magenta health models` to verify |
| Approval not appearing | Redis connectivity | Check infrastructure health |
| No missions created | Webhook not reaching API | `curl -X POST http://localhost:8000/webhooks/sentinel` to test |

### Getting Help

```bash
# General health
magenta health --format json

# Check model backends
magenta health models

# Check agent registry
magenta health agents

# Check pipeline connectivity
magenta health pipeline
```
