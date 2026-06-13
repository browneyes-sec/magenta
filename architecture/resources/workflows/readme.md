# Workflow Architecture & Sizing

## Component Overview

Magenta orchestrates multi-agent workflows through a state machine defined in `magenta/core/mission.py` (`MissionManager`) and driven by `magenta/orchestration/engine.py` (`OrchestrationEngine`).

## Mission State Machine

```
         ┌──────────┐
         │  Created  │
         └────┬─────┘
              │ scope()
              ▼
         ┌──────────┐
         │  Scoped   │
         └────┬─────┘
              │ assign()
              ▼
         ┌──────────┐
         │ Assigned  │
         └────┬─────┘
              │ start()
              ▼
         ┌──────────┐
         │ Executing │◄────────────┐
         └────┬─────┘              │
              │                    │
     ┌────────┼────────┐          │
     ▼        ▼        ▼          │
 ┌────────┐ ┌────────┐ ┌────────┐ │
 │ Task 1 │ │ Task 2 │ │ Task N │ │ retry
 └───┬────┘ └───┬────┘ └───┬────┘ │
     │          │          │      │
     └──────────┴──────────┘      │
              │ all complete      │
              ▼                   │
         ┌──────────┐             │
         │  Review   │────────────┘ if approval needed
         └────┬─────┘
              │ approve()
              ▼
         ┌────────────┐
         │ Completed   │
         └────────────┘

Fail/Error states:
┌──────────┐     ┌──────────┐
│  Failed   │     │ Escalated│
└──────────┘     └──────────┘
                              ┌──────────┐
                              │ Cancelled│
                              └──────────┘
```

## Saga Pattern (Compensating Transactions)

For multi-step response actions, Magenta implements the saga pattern to roll back partially completed actions when a downstream step fails.

```python
# magenta/response/executor.py (conceptual)
ACTIONS_WITH_COMPENSATION = {
    ActionType.disable_account: {
        "compensation": ActionType.enable_account,
        "idempotent": True,
        "max_retries": 3,
    },
    ActionType.isolate_host: {
        "compensation": ActionType.restore_host,
        "idempotent": False,  # re-isolation needs fresh assessment
        "max_retries": 1,
    },
    ActionType.block_ip: {
        "compensation": ActionType.unblock_ip,
        "idempotent": True,
        "max_retries": 2,
    },
}
```

### Saga Execution Flow

```python
async def execute_mission_saga(mission: Mission) -> bool:
    """Execute mission actions with saga rollback."""
    completed_actions: list[tuple[ActionType, Target]] = []
    try:
        for task in mission.tasks:
            result = await execute_action(task)
            if result.status == ActionStatus.failed:
                raise ActionError(task)
            completed_actions.append((task.action, task.target))
        return True
    except ActionError as e:
        # Rollback in reverse order
        for action, target in reversed(completed_actions):
            await compensate(action, target, mission.correlation_id)
        return False
```

## DAG-Based Task Decomposition

The Swarm Manager decomposes missions into a DAG of dependent tasks. From `magenta/core/swarm.py`:

```python
task_dag = {
    "triage": {"depends_on": [], "assignee": "triage_agent"},
    "enrich": {"depends_on": ["triage"], "assignee": "enrich_agent"},
    "contain": {"depends_on": ["enrich"], "assignee": "contain_agent"},
    "investigate": {"depends_on": ["enrich", "contain"], "assignee": "investigate_agent"},
    "compliance": {"depends_on": ["investigate"], "assignee": "compliance_agent"},
    "report": {"depends_on": ["compliance", "contain"], "assignee": "report_agent"},
}
```

```
triage ──► enrich ──┬──► contain ──┐
                    │              ├──► report
                    └──► investigate─► compliance ──┘
```

## Teaming Structures as Workflow Patterns

| Structure | Workflow Pattern | Implementation |
|---|---|---|
| Supervisor | Hierarchical orchestration | `SwarmManagerAgent.run_mission()` delegates to role agents |
| Debate | Parallel fan-out, consensus gather | Multiple agents analyze same data, vote on outcome |
| Pipeline | Sequential chain | `triage → enrich → contain → report` |
| Mesh | Peer-to-peer task marketplace | Agents broadcast tasks, idle agents pick them up |
| Referee | Human-in-the-loop | All actions gated through `ApprovalGate` |

## Human-in-the-Loop Escalation

```python
# magenta/response/executor.py (conceptual)
GATES = {
    "auto_resolve": {"risk_max": 40, "confidence_min": 0.9, "action": "proceed"},
    "agent_review": {"risk_max": 70, "action": "request_approval"},
    "human_lead": {"risk_max": 85, "action": "escalate"},
    "emergency": {"risk_min": 86, "action": "immediate_execute"},
}
```

## Configuration

```yaml
orchestration:
  max_concurrent_missions: 10
  max_tasks_per_mission: 50
  agent_timeout_seconds: 120
  task_retry_count: 3
  saga_rollback_enabled: true

escalation:
  tiers:
    auto_resolve:
      max_risk: 40
      min_confidence: 0.9
    agent_review:
      max_risk: 70
      auto_approve_timeout: 300
    human_lead:
      max_risk: 85
      notify_slack: true
    emergency:
      min_risk: 86
      execute_immediately: true
      notify_soc: true
```

## Monitoring

| Metric | Alert |
|---|---|
| Mission failure rate > 5% | Warning |
| Task retry rate > 20% | Warning |
| Saga rollback count > 5/day | Investigate |
| Human approval queue > 10 pending | Info — ops review |
| Mission duration > 30 min (non-emergency) | Warning |
| Deadline exceeded rate > 1% | Critical |
