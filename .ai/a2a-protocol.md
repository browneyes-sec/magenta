# A2A Protocol — Magenta AI Layer

**Agent-to-Agent (A2A) communication framework using JSON messages over Event Hubs. Based on Google A2A draft specification patterns.**

---

## 1. A2A Message Envelope

Every agent-to-agent message follows a standard envelope:

```json
{
  "protocol": "magenta-a2a/1.0",
  "message_id": "msg-8a3f2c91-7e4b-4d11-9f2a-1b3c5d7e9f01",
  "correlation_id": "mission-8932",
  "source": "agent:triage_agent/v3",
  "target": "agent:swarm_manager/v2",
  "message_type": "task_result",
  "timestamp": "2026-06-13T19:02:15.123Z",
  "ttl_seconds": 300,
  "priority": "normal",
  "trace": {
    "parent_message_id": "msg-1a2b3c4d-5e6f-7890-abcd-ef1234567890",
    "origin_agent": "source_agent:logic_app/v1",
    "turn": 3,
    "hops": ["source_agent", "triage_agent"]
  },
  "payload": {},
  "signature": "sha256-hmac-base64..."
}
```

---

## 2. Message Types

| Type | Direction | Content |
|---|---|---|
| `task_assign` | Manager → Agent | Task instructions + context |
| `task_accept` | Agent → Manager | Bid/accept with estimated SLA |
| `task_result` | Agent → Manager | Output + evidence + confidence |
| `task_fail` | Agent → Manager | Error details + partial results |
| `task_progress` | Agent → Manager | Intermediate status update |
| `escalate` | Any → Manager | Need human or specialist intervention |
| `approval_request` | Agent → Human | Approval gate request |
| `approval_response` | Human → Agent | Approved / Rejected / Modified |
| `discover` | Agent → Registry | Capability registration |
| `heartbeat` | Agent → Manager | Health + load status |
| `broadcast` | Manager → All | Alert / configuration update |
| `request_info` | Agent → Agent | Request evidence or context |
| `provide_info` | Agent → Agent | Response with evidence |
| `consensus_vote` | Agent → Consensus Gate | Verdict + confidence |
| `consensus_result` | Gate → All | Converged verdict |

---

## 3. Task Assignment

```json
{
  "message_type": "task_assign",
  "source": "agent:swarm_manager/v2",
  "target": "agent:containment_specialist/v1",
  "correlation_id": "mission-8932",
  "payload": {
    "task_id": "task-contain-001",
    "task_type": "contain",
    "mission": {
      "alert_id": "sentinel-incident-8932",
      "severity": "high",
      "risk_score": 72,
      "description": "Phishing campaign targeting Finance department",
      "iocs": [
        {"type": "url", "value": "hxxps://malicious-phish[.]com"},
        {"type": "hash", "value": "a1b2c3d4e5f6..."}
      ]
    },
    "instructions": "Assess if containment is needed. Possible actions: disable compromised accounts, isolate affected hosts, block IoCs at firewall.",
    "constraints": {
      "max_turns": 5,
      "require_approval": true,
      "approval_threshold": 60,
      "timeout_seconds": 120
    },
    "dependencies": ["task-enrich-001"],
    "context": {
      "enrichment_results": [
        {"source": "virustotal", "verdict": "malicious", "confidence": 0.91},
        {"source": "entra_id", "affected_users": ["admin@finance.contoso.com"]}
      ]
    }
  }
}
```

---

## 4. Task Result

```json
{
  "message_type": "task_result",
  "source": "agent:containment_specialist/v1",
  "target": "agent:swarm_manager/v2",
  "correlation_id": "mission-8932",
  "payload": {
    "task_id": "task-contain-001",
    "status": "completed",
    "actions_taken": [
      {
        "action": "disable_account",
        "target": "admin@finance.contoso.com",
        "tool": "entra_id.disable_account",
        "status": "approved",
        "risk_score": 65,
        "timestamp": "2026-06-13T19:05:00Z"
      },
      {
        "action": "block_url",
        "target": "hxxps://malicious-phish[.]com",
        "tool": "defender.block_indicator",
        "status": "succeeded",
        "risk_score": 20,
        "timestamp": "2026-06-13T19:05:02Z"
      }
    ],
    "open_issues": [
      "2 additional users may be affected pending investigation"
    ],
    "evidence_refs": [
      "adl://lake/evidence/8932/containment-summary.json"
    ],
    "llm_usage": {
      "model": "ollama/qwen2.5:7b",
      "tokens_in": 3200,
      "tokens_out": 540,
      "latency_ms": 4200,
      "turns": 3
    }
  }
}
```

---

## 5. Approval Flow

```json
// Agent requests approval
{
  "message_type": "approval_request",
  "source": "agent:containment_specialist/v1",
  "target": "human:soc_analyst",
  "correlation_id": "mission-8932",
  "payload": {
    "action": "disable_account",
    "target": {"type": "user", "id": "admin@finance.contoso.com", "criticality": "critical"},
    "risk_score": 65,
    "reasoning": "User clicked phishing link. 12/70 AV vendors flag URL as malicious. Account may be compromised.",
    "alternatives": [
      {"action": "force_password_reset", "risk_score": 30},
      {"action": "enable_mfa_reauth", "risk_score": 15}
    ],
    "evidence": ["virustotal:12/70", "sentinel:incident-8932"],
    "expires_at": "2026-06-13T19:10:00Z"
  }
}

// Human responds
{
  "message_type": "approval_response",
  "source": "human:soc_analyst",
  "target": "agent:containment_specialist/v1",
  "correlation_id": "mission-8932",
  "payload": {
    "decision": "approved",
    "action": "disable_account",
    "modified_parameters": {},
    "comment": "Approved. Also reset password after disable.",
    "approver_id": "entra-user-john.doe@contoso.com",
    "timestamp": "2026-06-13T19:07:00Z"
  }
}
```

---

## 6. Consensus Protocol (Debate Pattern)

```json
// Each analyst votes
{
  "message_type": "consensus_vote",
  "source": "agent:analyst_a/v2",
  "target": "gate:consensus_gate/v1",
  "correlation_id": "mission-8932",
  "payload": {
    "verdict": "malicious",
    "confidence": 0.85,
    "mitre_tactics": ["TA0001", "TA1566"],
    "reasoning": "URL domain registered 2 days ago. Credential harvesting page detected.",
    "model": "ollama/qwen2.5:7b"
  }
}

// Consensus gate broadcasts result
{
  "message_type": "consensus_result",
  "source": "gate:consensus_gate/v1",
  "target": "agent:swarm_manager/v2",
  "correlation_id": "mission-8932",
  "payload": {
    "final_verdict": "malicious",
    "agreement_score": 0.87,
    "votes": 3,
    "dissenting": [],
    "consensus_method": "weighted_confidence"
  }
}
```

---

## 7. Agent Discovery

```json
{
  "message_type": "discover",
  "source": "agent:containment_specialist/v1",
  "target": "registry:agent_registry",
  "payload": {
    "agent_id": "containment_specialist-v1",
    "role": "containment",
    "version": "1.2.0",
    "status": "online",
    "capabilities": [
      {"tool": "entra_id.disable_account", "risk_impact": 60},
      {"tool": "defender.isolate_host", "risk_impact": 80},
      {"tool": "sentinel.update_incident", "risk_impact": 10},
      {"tool": "registry.write_activity", "risk_impact": 0}
    ],
    "models": [
      {"provider": "ollama", "model": "qwen2.5:7b", "tier": "speed"},
      {"provider": "ollama", "model": "mistral:7b", "tier": "speed"}
    ],
    "load": 0.3,
    "max_concurrent_tasks": 5,
    "current_tasks": 2,
    "uptime_seconds": 86400
  }
}
```

---

## 8. Heartbeat Protocol

```json
{
  "message_type": "heartbeat",
  "source": "agent:triage_agent/v3",
  "target": "agent:swarm_manager/v2",
  "payload": {
    "status": "healthy",
    "load": 0.4,
    "tasks_completed": 128,
    "tasks_failed": 1,
    "avg_latency_ms": 1800,
    "p95_latency_ms": 3200,
    "model_health": {
      "ollama/qwen2.5:7b": {"status": "healthy", "latency_ms": 1200},
      "ollama/mistral:7b": {"status": "degraded", "latency_ms": 4500}
    },
    "tool_health": {
      "sentinel_query": {"status": "healthy", "error_rate": 0.01},
      "registry_write": {"status": "healthy", "error_rate": 0.00}
    },
    "uptime_seconds": 43200,
    "memory_usage_mb": 512
  }
}
```

---

## 9. A2A Transport

| Transport | Latency | Reliability | Use Case |
|---|---|---|---|
| Event Hubs (Kafka) | ~100ms | At-least-once | Primary inter-agent messaging |
| Redis Pub/Sub | ~5ms | At-most-once | Heartbeats, live status |
| HTTP (direct) | ~50ms | Synchronous | Approval responses, urgent escalations |
| Azure Queue | ~500ms | At-least-once | Dead-letter, retry queue |

```yaml
a2a_transport:
  primary: "event_hubs"
  config:
    namespace: "magenta-agent-bus"
    topic: "agent-messages"
    partitions: 8
    retention_hours: 24
    consumer_groups:
      - "swarm_managers"
      - "agents"
      - "human_approvals"
      - "registry"
  heartbeat:
    topic: "agent-heartbeats"
    retention_minutes: 60
    interval_seconds: 30
    miss_threshold: 3
```

---

## 10. A2A Security

| Concern | Control |
|---|---|
| Message integrity | HMAC-SHA256 signature on every envelope |
| Replay prevention | `message_id` + dedup window (60s) |
| Authorization | Source verified against agent registry |
| Confidentiality | Payload encryption for cross-network hops |
| Rate limiting | Per-agent message cap (100/s burst, 10/s sustained) |
| Schema validation | JSON Schema enforced at transport layer |
