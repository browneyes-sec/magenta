# Loop Engineering — Magenta ASOAR Feedback & Control Loops

**Document Type:** Engineering Reference
**Version:** 1.0
**Classification:** Internal Architecture Reference

---

## Purpose

Loop engineering defines the feedback and control loops that make the Magenta platform self-correcting, observable, and continuously improving. Every agent action, mission lifecycle, and platform operation participates in one or more loops.

---

## 1. Architecture Overview

Magenta implements four tiers of loops:

```
Agent Loop (milliseconds)
    ↓
Mission Loop (seconds–minutes)
    ↓
Registry Loop (minutes–hours)
    ↓
Governance Loop (days–months)
```

Each loop feeds into the next, creating a closed-loop system where operational data informs governance decisions, which constrain agent behavior.

---

## 2. Agent Loop (Fastest)

The agent loop governs how an individual agent processes a mission and learns from the outcome.

```
Alert → Agent.process() → LLM.generate() → Action → log_activity() → Registry
                            ↑                                      │
                            └────── Feedback (next turn) ←──────────┘
```

### Key Characteristics
| Property | Value |
|----------|-------|
| Frequency | Per-agent, per-task (milliseconds–seconds) |
| Scope | Single agent, single task |
| Feedback | Next LLM call incorporates prior results |
| Failure mode | Agent retries with backoff (3 attempts) |

### Components
- `BaseAgent.process(mission, context)` — entry point
- `LLMAgent.llm_generate()` — LLM inference with sensitivity-aware routing
- `LLMAgent.log_activity()` — telemetry write (non-blocking)
- `AgentStatus` — idle → ready → executing → done/error

### Optimization Target
Reduce per-turn latency: target < 2s for `speed` tier, < 15s for `reasoning` tier.

---

## 3. Mission Loop (Operational)

The mission loop governs the lifecycle of a single alert from ingestion to resolution.

```
Ingest → Decompose → Assign → Execute (parallel) → Aggregate → Registry
  ↑                                                              │
  └─────────────────────── Retry / Escalate ←────────────────────┘
```

### Key Characteristics
| Property | Value |
|----------|-------|
| Frequency | Per-alert (seconds–minutes) |
| Scope | Multi-agent swarm |
| Feedback | Failed tasks → retry with different agent |
| Failure mode | Escalation to human analyst |

### State Machine
```
created → scoped → assigned → executing → completed
                                    ↓
                              failed / escalated
```

### Approval Gate Loop (High-Risk Extension)
```
risk_score > threshold → ApprovalRequest → Approval API → human decision
                               ↑                                  │
                               └────────── EventHub ←─────────────┘
                                       ↓
                              Orchestrator resumes / terminates
```

### Optimization Target
P50 < 5 min (auto-approved), P95 < 12 min (including approval wait).

---

## 4. Registry Loop (Observability)

The registry loop ensures every action is recorded and can be replayed.

```
Agent.action → RegistryWriter (ES + Sentinel + Delta) → Dead-letter queue
                                                              │
                            ┌─────────────────────────────────┘
                            ↓
                     Retry worker → re-queue failed writes
```

### Key Characteristics
| Property | Value |
|----------|-------|
| Frequency | Per-action (milliseconds) |
| Scope | All sinks |
| Feedback | Dead-letter → retry or alert |
| Failure mode | Fire-and-forget; agent never blocks |

### Throttling & Backpressure
- SOAR connector: CircuitBreaker (OPEN after 5 consecutive failures)
- EventHub consumer: auto-inflate on lag; dead-letter on schema failure
- RegistryWriter: `return_exceptions=True` — never blocks agent

---

## 5. Governance Loop (Strategic)

The governance loop ensures the platform evolves within architectural guardrails.

```
Architecture → ADRs → CI/CD gate → Deploy → Monitor → Review → Update ADRs
                                                              ↓
                                               TOGAF Phase H (monthly)
```

### Key Characteristics
| Property | Value |
|----------|-------|
| Frequency | Monthly (Phase H) |
| Scope | Platform-wide |
| Feedback | Deviation log → exception register → policy update |
| Failure mode | Architecture Change Board intervention |

### Governance Controls

| Control | Mechanism | Frequency |
|---------|-----------|-----------|
| Schema conformance | Dead-letter rate < 1% | Per-deploy |
| Playbook version pinning | CI/CD gate blocks unversioned commits | Per-commit |
| RBAC compliance | Azure Policy audit on managed identities | Weekly |
| Architecture review | ADR + deviation log | Monthly |
| Audit integrity | Key Vault signing per Delta batch | Per-batch |
| LLM policy compliance | CI/CD gate bypass detection | Per-commit |

---

## 6. Circuit Breaker Loop (Resilience)

The circuit breaker loop protects integrations from cascade failures.

```
Normal (CLOSED) → 5 failures → OPEN → 30s timeout → HALF_OPEN → probe → CLOSED
                                                                      ↓
                                                               OPEN (probe failed)
```

### Integration Points
| Connector | Failure Threshold | Reset Timeout |
|-----------|-------------------|---------------|
| SOAR API | 5 | 30s |
| Sentinel API | 5 | 30s |
| Splunk API | 5 | 30s |
| Elasticsearch | 3 | 60s |

---

## 7. Idempotency Loop (Safety)

The idempotency loop prevents duplicate actions during restarts and retries.

```
Execution Agent → check_and_register() → Key exists? → No → Execute
                                                Yes      ↓
                                           Skip (log duplicate)
```

### TTL Chain
```
EventHubs retention (7d) → Idempotency TTL (24h) → Action complete
```

---

## 8. Loop Metrics & Alerting

| Loop | Metric | Alert Threshold |
|------|--------|-----------------|
| Agent | `agent.llm_latency_ms` | > 10s for speed tier |
| Mission | `mission.latency_ms` | > 15 min for Sev 3+ |
| Registry | `registry.write_success_rate` | < 99% over 5 min |
| Registry | `registry.dead_letter_count` | > 10 in 5 min |
| Circuit Breaker | `circuit_breaker.state` | Any OPEN state > 5 min |
| Idempotency | `idempotency.duplicate_count` | > 1 in 1 hour |
| EventHub | `eventhub.consumer_lag` | > 1000 per partition |

---

## 9. Development & CI/CD Loop

The development loop integrates context engineering with code generation.

```
CLAUDE.md → Agent reads → Code generation → Test → Review → Merge → Deploy
    ↑                                                            │
    └─────────────────── ADR update ←─────────────────────────────┘
```

### SDLC Guardrails
- All PRs must pass 66 existing tests + new integration tests
- All new API endpoints must have OpenAPI spec
- All new connectors must have circuit breaker + health check
- All new agent prompts must include security guardrails
- Schema changes require ADR and version bump

---

## References

- `/architecture/readme.md` — DTP and architecture vision
- `/docs/engineering/integration-plan.md` — Sprint-structured implementation plan
- `/docs/architecture/adrs/` — Architecture Decision Records
- `/context/llm-policy.md` — Sensitivity routing and redaction policy
- `/magenta/core/circuit_breaker.py` — Circuit breaker implementation
- `/magenta/core/idempotency_store.py` — Idempotency store implementation
- `/magenta/core/registry.py` — Registry triple-write implementation
