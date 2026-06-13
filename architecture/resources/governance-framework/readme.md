# Governance Framework

## Component Overview

The governance framework maps the Magenta fabric to enterprise architecture standards: **TOGAF ADM** for architecture lifecycle and **Azure Well-Architected Framework (WAF)** for operational quality.

DTP references: §3 (WAF Pillars), §4 (TOGAF ADM), §7.3, §8 (Implementation Governance), §9 (Risk Register)

## TOGAF ADM Mapping

| ADM Phase | DTP Section | Magenta Deliverable | Governance Artifact |
|---|---|---|---|
| **A — Architecture Vision** | §1 | Problem statement, target state, guiding principles | Architecture vision document |
| **B — Business Architecture** | §5 | Stakeholder map, SOC operating model changes, BU enablement | RACI matrix, operating model |
| **C — Information Systems** | §2 | Agent catalogue, canonical schema, data flow diagrams | Data flow diagrams, schema registry |
| **D — Technology Architecture** | §2, §10 | Component stack, Event Hubs, Data Lake, ES, Sentinel | Architecture decision records (ADR) |
| **E — Opportunities & Solutions** | §6 | Build vs. buy decisions, risk-scored implementation options | Solution selection matrix |
| **F — Migration Planning** | §7 | 30-60-90 day phased roadmap with milestones | Migration plan, phase gates |
| **G — Implementation Governance** | §8 | Compliance checkpoints, acceptance criteria, RBAC validation | Architecture contract, deviation log |
| **H — Architecture Change** | §8 | Monthly architecture review, deviation log, exception register | Change board minutes, ADR updates |

## Architecture Decision Records (ADR)

Located in `architecture/ADR/`:

```markdown
# ADR-001: Event Hubs as Automation Bus

**Status:** Accepted
**Date:** 2026-06-01

## Context
The fabric needs a durable, ordered message backbone for agent communication.

## Decision
Use Azure Event Hubs (Standard tier, Kafka endpoint) over self-managed Kafka.

## Rationale
- Managed service reduces operational overhead
- Kafka-compatible endpoint enables standard tooling
- Event Hubs Capture provides zero-code archival to Data Lake
- Auto-inflate handles variable alert volume

## Consequences
- Vendor lock-in to Azure messaging
- Partition count must be set at creation time
- Kafka protocol has feature gaps vs. native Event Hubs SDK

## Compliance
DTP §2.1, §10
```

## WAF Pillar Compliance

### Reliability

| Requirement | Magenta Implementation | Verification |
|---|---|---|
| Event Hubs absorbs bursts | Auto-inflate to 8 TUs, dead-letter topic | Load test at 2× peak volume |
| Idempotency prevents duplicates | SHA-256 key, 24h TTL, atomic SETNX | Automated idempotency test suite |
| Source agent failure | Last-poll-time tracking, backoff, retry | Chaos: kill source agent, verify catch-up |
| Registry dual-write consistency | Write to ES + Sentinel + Lake, compare hashes | Batch integrity check every 6 hours |

### Security

| Requirement | Magenta Implementation | Verification |
|---|---|---|
| Managed identities only | Per-agent app registration, no stored secrets | Azure Policy audit on MI permissions |
| Prompt injection protection | Input sanitization, instruction boundaries, output validation | Prompt injection test suite |
| Approval gate for risk | Risk score > 50 requires human approval | Penetration test on approval bypass |
| Least-privilege RBAC | ROLE_PERMISSIONS matrix per agent and human role | Quarterly RBAC review |

### Cost Optimization

| Requirement | Magenta Implementation | Verification |
|---|---|---|
| Lake-first storage | Event Hubs Capture → Data Lake Parquet | Actual vs. budgeted storage costs |
| Tiered Elasticsearch ILM | Hot 7d → Warm 30d → Cold 365d → Delete | ILM policy compliance report |
| Free-tier LLM fallback | Groq/Gemini free tier as fallback when OLLAMA saturated | Cost dashboard per model provider |
| Consumption-plan Functions | Pay-per-execution for source agents | Function cost allocation per agent |

### Operational Excellence

| Requirement | Magenta Implementation | Verification |
|---|---|---|
| Playbook versioning | Git-controlled, version pinned in every `automation.activity` event | CI/CD gate: blocks unversioned deployments |
| Observability | Azure Monitor + App Insights + Elasticsearch dashboards | Dashboard availability SLA |
| Agent health monitoring | Per-agent heartbeat, consumer lag, dead-letter rate | Runbook: agent malfunction response |
| Architecture change review | Monthly TOGAF Phase H review board | Architecture change register |

### Performance Efficiency

| Requirement | Magenta Implementation | Verification |
|---|---|---|
| Partitioned Event Hubs | Correlation_id as partition key per topic | Partition skew < 20% |
| Enrichment cache | Redis TTL cache for CMDB/threat intel queries | Cache hit rate > 60% |
| Async orchestration | asyncio-based mission runner with circuit breakers | Mission duration P95 < 10 min |
| Model routing tiers | speed → reasoning → cost_save fallback chain | Model latency P99 per tier |

## Acceptance Criteria Per Phase Gate

### Day 30 Gate (Foundation)

| Criterion | Measure |
|---|---|
| Sentinel incidents in `raw-alerts` | < 2 min from creation |
| Splunk fired alerts in `raw-alerts` | < 5 min from firing |
| SOAR audit events in Elasticsearch | < 10 min |
| Schema validation pass rate | > 99% (dead-letter < 1%) |
| Sentinel custom table queryable | KQL query returns `SecurityAutomationActivity_CL` |

### Day 60 Gate (Pilot)

| Criterion | Measure |
|---|---|
| End-to-end `automation.activity` in all 3 registries | < 15 min from SIEM alert |
| Zero duplicate executions | Idempotency verified |
| Approval gate fires correctly | Risk score > 70 blocked, < 40 auto-approved |
| Playbook version captured | Every event has `playbook_id` + version |
| Execution agent accuracy | SOC analyst validates > 90% of actions |

### Day 90 Gate (Launch)

| Criterion | Measure |
|---|---|
| Three BUs using dashboards | Active dashboard queries per BU |
| Governance artifacts complete | RACI, runbook, agent policy YAML, IR playbook |
| KPI baseline established | Published to CISO |
| BU onboarding documentation complete | Self-service playbook |
| Steady-state handoff | Agent Ops Engineer role active |

## RBAC Review Cadence

| Review | Frequency | Owner | Scope |
|---|---|---|---|
| Managed identity permissions | Weekly (automated) | Azure Policy | Every agent identity vs. assigned scopes |
| Human role assignments | Monthly | SOC Manager | User role changes, terminations |
| API key rotation | Quarterly | Security Team | Machine-to-machine keys |
| Full RBAC audit | Semi-annual | Internal Audit | Entra ID audit logs, privilege escalation alerts |

## Architecture Change Board

**Meeting:** Monthly, 30 min
**Attendees:** Architect, SOC Manager, Agent Ops Engineer, BU representative (rotating)
**Trigger for off-cycle review:** New agent role, new data source, new action type with blast_radius > subnet

### Change Request Template

```markdown
## Architecture Change Request
**Date:** YYYY-MM-DD
**Requester:** [Name/Role]
**Category:** New Agent | New Data Source | New Action | Infrastructure Change

## Description
[Brief description of proposed change]

## Impact Assessment
- Affected components: [Event Hubs, Elasticsearch, etc.]
- WAF pillar impact: [Reliability, Security, Cost, Operations, Performance]
- Risk score change: [If action type changes]

## Approval
- [ ] Architecture Board Chair
- [ ] SOC Manager
- [ ] Security (if security impact)
```

## Risk Register (from DTP §9)

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| SIEM API rate limits | Med | High | Backoff + DLQ + streaming fallback | Agent Ops Engineer |
| SOAR audit endpoint downtime | Med | Med | Cache last state + alert on gap | Agent Ops Engineer |
| LLM hallucinated routing | Low | High | Shadow mode + rules fallback + confidence logging | Architect |
| Event Hubs consumer lag | Med | Med | Auto-inflate + premium tier + severity partitions | Platform Team |
| Duplicate action execution | Med | High | Idempotency key + check-before-act | Architect |
| BU over-reliance on automation | Low | High | Monthly sample review + FP rate threshold | SOC Manager |

## Monitoring

| Metric | Alert |
|---|---|
| Phase gate slippage > 1 week | Escalate to program manager |
| Architecture deviation count > 3/month | Trigger off-cycle change board |
| RBAC privilege escalation > 0 | Immediate security incident |
| Unaddressed risk register items > 5 | Warning — review backlog |
| WAF pillar score < 3/5 (any pillar) | Schedule remediation sprint |
