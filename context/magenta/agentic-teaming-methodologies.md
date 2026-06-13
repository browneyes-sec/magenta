# Agentic Teaming Methodologies — Magenta Framework

Five teaming structures for cybersecurity multi-agent collaboration, inspired by military C2, sports teams, and open-source swarm patterns.

---

## 1. Supervisor (Hierarchical Command)

### Structure

```
          ┌───────────────────┐
          │   Swarm Manager   │  ◄── Strategist (LLM: mixtral/qwen32b)
          └────┬──────┬───────┘
               │      │
     ┌─────────▼┐  ┌──▼────────┐
     │ Triage   │  │ Contain   │  ◄── Specialists (LLM: qwen7b/mistral)
     │ Agent    │  │ Agent     │
     └──────────┘  └───────────┘
     ┌─────────┐  ┌──────────┐
     │ Enrich  │  │ Report   │
     │ Agent   │  │ Agent    │
     └─────────┘  └──────────┘
```

### Protocol

1. **Swarm Manager** receives mission, decomposes into tasks
2. **Manager assigns** tasks to specialists with explicit instructions
3. **Specialists execute** tasks, report results back to manager
4. **Manager integrates** results, decides next steps
5. **Manager escalates** to human when risk threshold exceeded
6. **Manager completes** mission when all tasks done

### Best For
- Complex, multi-step incidents (APT investigation, ransomware response)
- When tight coordination and sequencing matter
- When one agent must have the full picture

### Configuration

```yaml
supervisor:
  manager:
    role: "swarm_manager"
    model: "ollama/mixtral:8x7b"
    max_turns: 30
  delegation:
    strategy: "direct_assign"
    max_parallel_tasks: 3
  escalation:
    risk_threshold: 70
    human_handoff: true
```

---

## 2. Debate (Democratic Consensus)

### Structure

```
            Alert ──┐
                    │
     ┌──────────────▼────────────────┐
     │         Consensus Gate          │
     │   (wait for N agents to vote)   │
     └──────┬──────────────┬──────────┘
            │              │
     ┌──────▼──────┐ ┌────▼──────────┐
     │ Analyst A   │ │ Analyst B     │
     │ (LLM model) │ │ (LLM model)   │
     └──────┬──────┘ └────┬──────────┘
            │              │
     ┌──────▼──────┐ ┌────▼──────────┐
     │ Analyst C   │ │ Analyst D     │
     │ (LLM model) │ │ (LLM model)   │
     └──────┬──────┘ └────┬──────────┘
            │              │
            └──────┬──────┘
                   ▼
          ┌────────────────┐
          │  Convergence   │
          │  (agreement?   │
          │   confidence?) │
          └───────┬────────┘
                  │
          ┌───────▼────────┐
          │ Verdict +      │
          │ Evidence Chain │
          └────────────────┘
```

### Protocol

1. **All analysts receive** the same alert + context independently
2. **Each analyst produces** a verdict (malicious/benign/unknown) with confidence and reasoning
3. **Consensus gate calculates** weighted agreement score
4. **If agreement >= threshold (0.8) →** verdict accepted
5. **If agreement < threshold →** analysts see each other's reasoning, second round
6. **If still deadlocked after N rounds →** human tiebreaker

### Consensus Formula

```python
def consensus(verdicts: list[Verdict]) -> ConsensusResult:
    weights = {
        v.agent_id: v.historical_accuracy * v.confidence
        for v in verdicts
    }
    total_weight = sum(weights.values())
    
    score_per_outcome = {}
    for v in verdicts:
        score_per_outcome[v.outcome] = score_per_outcome.get(v.outcome, 0) + weights[v.agent_id]
    
    winning = max(score_per_outcome, key=score_per_outcome.get)
    agreement = score_per_outcome[winning] / total_weight
    
    return ConsensusResult(
        outcome=winning,
        agreement=agreement,
        dissenting= [v for v in verdicts if v.outcome != winning],
        confidence= agreement
    )
```

### Best For
- False positive reduction (phishing, alert verification)
- High-stakes decisions where error cost is high
- Evading single-model blind spots (different models catch different errors)

### Configuration

```yaml
debate:
  agents: 3
  models:
    - "ollama/qwen2.5:7b"
    - "ollama/mistral:7b"
    - "ollama/deepseek-r1:7b"
  rounds: 2
  agreement_threshold: 0.8
  tiebreaker: "human"
  cross_examine: true  # agents see others' reasoning
```

---

## 3. Pipeline (Sequential Handoff)

### Structure

```
  Alert ──► [Triage] ──► [Enrich] ──► [Contain] ──► [Report]
              │            │             │              │
              ▼            ▼             ▼              ▼
         severity+    context+      actions+        summary+
         routing      evidence      outcome         artifacts
```

### Protocol

1. **Each stage** receives the artifact bundle from previous stage
2. **Stage agent** adds its contribution to the bundle (immutable append)
3. **Stage agent** decides: continue pipeline, escalate, or halt
4. **Pipeline manager** tracks progress and SLA
5. **Failed stage** can be retried with a different agent model

### Artifact Bundle Schema

```json
{
  "correlation_id": "mission-8932",
  "stages": {
    "triage": {
      "agent": "triage_agent-v3",
      "model": "ollama/qwen2.5:7b",
      "verdict": "high_severity_phishing",
      "risk_score": 72,
      "confidence": 0.85,
      "timestamp": "2026-06-13T19:00:00Z"
    },
    "enrich": [
      {
        "agent": "enrich_agent-v2",
        "model": "ollama/mistral:7b",
        "source": "virustotal",
        "finding": "URL flagged by 12/70 vendors",
        "confidence": 0.91
      },
      {
        "agent": "enrich_agent-v2",
        "model": "ollama/mistral:7b",
        "source": "entra_id",
        "finding": "Target user: admin@finance.contoso.com (critical asset)",
        "confidence": 1.0
      }
    ],
    "contain": {
      "agent": "containment_specialist-v1",
      "model": "ollama/qwen2.5:7b",
      "actions": [
        {"tool": "defender.isolate_host", "target": "FIN-PROD-347", "status": "succeeded"},
        {"tool": "entra_id.disable_account", "target": "admin@finance.contoso.com", "status": "approved"}
      ]
    },
    "report": {
      "agent": "reporting_agent-v1",
      "model": "ollama/mistral:7b",
      "summary": "Phishing incident contained. Account disabled, host isolated. No data exfiltration detected.",
      "artifacts": ["adl://lake/evidence/8932/timeline.json", "adl://lake/evidence/8932/iocs.json"]
    }
  }
}
```

### Best For
- Well-defined, repeatable incident types
- Playbook replacement (traditional SOAR → Magenta pipeline)
- Compliance-mandated step sequences

### Configuration

```yaml
pipeline:
  stages:
    - role: "triage_agent"
      sla_seconds: 30
    - role: "enrich_agent"
      sla_seconds: 120
    - role: "containment_agent"
      sla_seconds: 60
      approval_required: true
    - role: "reporting_agent"
      sla_seconds: 60
  halt_on_failure: false
  artifact_backend: "redis"
```

---

## 4. Mesh (Peer-to-Peer Task Marketplace)

### Structure

```
                    ┌─────────────────────┐
                    │   Task Marketplace   │
                    │  (Event Hubs topic)  │
                    └─────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                 │
   ┌──────▼──────┐  ┌─────▼───────┐  ┌─────▼───────┐
   │ Agent Pool  │  │ Agent Pool  │  │ Agent Pool  │
   │ (Triage)    │  │ (Enrich)    │  │ (Contain)   │
   │ 3 instances │  │ 2 instances │  │ 2 instances │
   └─────────────┘  └─────────────┘  └─────────────┘
          │                │                 │
          └────────────────┼────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Reporter   │
                    │ (1 instance)│
                    └─────────────┘
```

### Protocol

1. **Swarm Manager publishes** task descriptions to a task topic
2. **Agents bid** on tasks they're qualified for (bid = estimated time + confidence)
3. **Manager assigns** task to lowest-bid/highest-confidence agent
4. **Agent executes** and publishes result
5. **If agent fails** to deliver within SLA, task is re-published
6. **Load balancing** — busy agents don't bid, preventing overload

### Bid Message

```json
{
  "message_type": "task_bid",
  "task_id": "task-enrich-003",
  "agent_id": "enrich_agent-v2-instance-4",
  "bid": {
    "estimated_seconds": 45,
    "confidence": 0.88,
    "current_load": 0.3
  }
}
```

### Best For
- High-volume alert surges (alert storm, DDoS, worm outbreak)
- Heterogeneous agent pools with different model backends
- Environments with variable agent availability (spot instances)

### Configuration

```yaml
mesh:
  bidding:
    enabled: true
    auction_timeout_ms: 5000
    tiebreaker: "lowest_load"
  agent_pools:
    triage:
      min_instances: 2
      max_instances: 10
      scaling: "task_queue_depth"
    enrich:
      min_instances: 2
      max_instances: 5
```

---

## 5. Referee (Human-in-the-Loop)

### Structure

```
                    Alert
                      │
                      ▼
              ┌────────────────┐
              │  Agent Team    │
              │  (all agents   │
              │  collaborate)  │
              └───────┬────────┘
                      │ findings + recommendations
                      ▼
              ┌────────────────┐
              │    REFEREE     │  ◄── Human (SOC Analyst)
              │   Decision     │
              └───────┬────────┘
                      │ approved / rejected / modified
                      ▼
              ┌────────────────┐
              │  Execute +     │
              │  Report        │
              └────────────────┘
```

### Protocol

1. **Agent team prepares** a full briefing: incident summary, evidence, recommended actions (with risk scores), alternatives
2. **Referee reviews** the briefing in a structured interface
3. **Referee decides**:
   - **Approve** — agents execute as recommended
   - **Reject** — agents document rejection, close mission
   - **Modify** — referee changes action parameters, agents execute modified plan
   - **Override** — referee takes manual control, agents switch to monitoring mode
4. **Agents execute** the decision and report outcomes
5. **Referee feedback** loop — analysts rate agent recommendations (improves confidence scoring)

### Referee Interface (Approval Request)

```markdown
## Mission: PHISH-8932 — Phishing Incident

### Severity: High (72/100)

### Evidence Summary
- URL: hxxps://malicious-phish[.]com detected in email to 12 users
- VirusTotal: 12/70 vendors flag as malicious
- Target Dept: Finance (4 critical asset users)
- Initial access vector: Spear-phish with credential harvesting page

### Recommended Actions

  1. [RECOMMENDED] Block URL at firewall (risk: 20)
  2. [RECOMMENDED] Disable 4 Finance user accounts (risk: 65) ⚠️
  3. [ALTERNATIVE] Isolate 4 Finance endpoints (risk: 80) ⛔
  4. [ALTERNATIVE] Create ServiceNow ticket for follow-up (risk: 5)

### Your Decision
[ Approve All ] [ Approve Selected ] [ Reject ] [ Override ]
```

### Best For
- High-risk actions where compliance demands human sign-off
- SOC team training — agents prepare briefs, analysts learn pattern recognition
- Sensitive environments (government, healthcare, critical infrastructure)

### Configuration

```yaml
referee:
  briefing_style: "structured_markdown"
  required_approvals:
    - action: "disable_account"
      risk_threshold: 40
    - action: "isolate_host"
      risk_threshold: 30
    - action: "block_ip"
      risk_threshold: 50
    - action: "create_ticket"
      risk_threshold: 100  # never requires approval
  escalation_timeout_minutes: 15
  auto_approve_on_timeout: false  # default: escalate to next SOC tier
```

---

## 6. Team Selection Strategy

Magenta's Swarm Manager selects the teaming structure dynamically based on alert characteristics:

```yaml
teaming_rules:
  - alert_condition: "severity >= 4 AND confidence < 0.8"
    structure: "debate"
    reason: "High uncertainty needs convergence"
  - alert_condition: "incident_type == 'ransomware' OR incident_type == 'apt'"
    structure: "supervisor"
    reason: "Complex multi-step requires orchestration"
  - alert_condition: "severity <= 2 AND confidence > 0.9"
    structure: "pipeline"
    reason: "Routine, well-understood playbook"
  - alert_condition: "alert_volume > 50_per_minute"
    structure: "mesh"
    reason: "Surge needs load-balanced processing"
  - alert_condition: "asset_criticality == 'critical' AND risk_score > 70"
    structure: "referee"
    reason: "High-impact requires human approval"
```

---

## 7. Teaming Anti-Patterns

| Anti-Pattern | Problem | Solution |
|---|---|---|
| **Too many cooks** | 10+ agents debating a low-severity alert | Match swarm size to alert criticality |
| **Bystander effect** | Mesh: every agent assumes another will pick up the task | Assertive bid timeouts; unclaimed tasks escalate |
| **Echo chamber** | Same model architecture in debate → same blind spots | Diverse model selection (different families, sizes) |
| **Approval fatigue** | Referee sees 100+ approval requests per shift | Auto-approve below configurable risk threshold |
| **Supervisor bottleneck** | Swarm Manager can't keep up with task assignments | Decompose into sub-swarms with deputy managers |
| **Misaligned incentives** | Agents rewarded for speed over accuracy | Confidence-weighted scoring in performance metrics |
