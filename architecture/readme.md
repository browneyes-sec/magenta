# DTP — AI Agent Security Telemetry Fabric: SIEM/SOAR Automation Registry

**Document Type:** Design Technical Plan (DTP)
**Version:** 1.0
**Classification:** Internal Architecture Reference
**Prepared by:** Senior AI Architect
**Timeline:** 30-day Build · 60-day Pilot · 90-day Business Unit Enablement
**Stack:** Microsoft Sentinel (primary SIEM) · Splunk + Splunk SOAR (PoC) · Azure Event Hubs · Data Lake · Elasticsearch

***

## Executive Summary

This DTP specifies the architecture and delivery plan for an **AI Agent Security Telemetry Fabric** — a vendor-agnostic platform that autonomously collects detections and incidents from SIEM platforms (Microsoft Sentinel and Splunk), orchestrates automation and response through SOAR, and registers every orchestration step in durable, queryable registries (Azure Data Lake, Elasticsearch, and Sentinel custom tables). The solution follows TOGAF ADM Phases A–G, the Azure Well-Architected Framework (WAF) five pillars, and a 30-60-90 day agentic AI deployment cadence.

**Business objective:** Enable SOC and business unit security owners to view every automated agent action, playbook execution, and orchestration outcome as first-class auditable telemetry — searchable, replayable, and reportable — rather than ephemeral SIEM/SOAR log entries.

***

## 1. Architecture Vision (TOGAF Phase A)

### 1.1 Problem Statement

SIEM and SOAR platforms are detection and response systems, not systems of record for automation behavior. Alerts from Sentinel or Splunk trigger playbooks, but the actions those playbooks take — disabling accounts, isolating hosts, creating tickets — are typically visible only inside the SOAR itself and expire with its internal retention window. There is no platform-agnostic, immutable registry of what was decided, by which agent, on what evidence, and with what outcome.

### 1.2 Target State

An event-driven multi-agent fabric sits between SIEM (source of detections) and downstream registries (destination for automation telemetry). Every agent role is stateless, independently deployable, and observable. The fabric emits a canonical `automation.activity` event for every action — approved or blocked — with full lineage back to the originating alert.

### 1.3 Guiding Principles

| Principle | Rationale |
|---|---|
| Ingest once, serve many | Raw logs enter one platform; all consumers read from it rather than re-collecting |
| API-first integration | Pull from SIEM/SOAR APIs or underlying storage over fan-out syslog sinks |
| Immutable audit by default | Every agent action appended to write-once storage with hash-linked provenance |
| Least-privilege identity | Short-lived credentials per agent, scoped RBAC, no shared service accounts |
| Human-in-the-loop for risk | High-impact actions require approval gate; low-risk actions fully automated |
| Cost tiers match value | Hot index for operational queries; cold lake for compliance and replay |

***

## 2. Architecture Components

### 2.1 Conceptual Architecture Diagram (Text Representation)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SECURITY DATA SOURCES                                │
│  [Microsoft Sentinel]  [Splunk Enterprise]  [EDR/NDR/IdP/Cloud]             │
└────────────┬───────────────────┬──────────────────────┬───────────────────┘
             │ Incidents/Alerts  │ Search Jobs/Alerts    │ Raw Logs
             ▼                   ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INGESTION PLANE                                      │
│  Source Agent          Source Agent          AMA / Syslog Forwarder         │
│  (Sentinel API /       (Splunk REST API /    (Log Analytics / Event Hubs)   │
│   Logic App trigger)    HEC / search/jobs)                                  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ Canonical Security Event (JSON / ASIM)
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│               SECURITY AUTOMATION BUS — Azure Event Hubs                    │
│  Topic: raw-alerts  │  Topic: enriched-alerts  │  Topic: actions  │  Topic: audit │
└──────┬──────────────┬──────────────────────────┬──────────────────┬────────┘
       │              │                          │                  │
       ▼              ▼                          ▼                  ▼
┌──────────┐  ┌──────────────┐         ┌──────────────────┐  ┌───────────────┐
│Normalizer│  │  Enrichment  │         │  Orchestrator    │  │  Registry     │
│  Agent   │  │    Agent     │         │    Agent         │  │   Agent       │
│(ASIM map)│  │(CMDB/TI/IAM) │         │(route to SOAR /  │  │(write to lake │
│          │  │              │         │ Func / Logic App) │  │ + Elastic +   │
└──────────┘  └──────────────┘         └────────┬─────────┘  │ Sentinel tbl) │
                                                 │            └───────────────┘
                                    ┌────────────▼─────────────────┐
                                    │       SOAR / Workers          │
                                    │  [Splunk SOAR]  [Logic Apps]  │
                                    │  [Azure Functions (custom)]   │
                                    └────────────┬─────────────────┘
                                                 │ Execution events
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REGISTRY LAYER                                      │
│  HOT:  Elasticsearch / Sentinel Custom Tables (operational search)          │
│  COLD: Azure Data Lake Gen2 — Parquet / Delta (compliance, replay, ML)      │
│  AUDIT: Sentinel Log Analytics — custom table SecurityAutomationActivity    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Agent Catalogue

| Agent | Function | Trigger | Output Topic |
|---|---|---|---|
| **Source Agent (Sentinel)** | Pulls incidents and alerts from Sentinel Incidents API on schedule; receives push via Logic App trigger | Timer / webhook | `raw-alerts` |
| **Source Agent (Splunk)** | Calls Splunk REST `/services/search/jobs` and `/rest/fired_alerts`; polls for new search results | Timer (30-second interval) | `raw-alerts` |
| **SOAR Audit Agent** | Calls Splunk SOAR `/rest/audit` endpoint; pulls playbook and container audit trails | Timer (5-minute interval) | `audit` |
| **Normalizer Agent** | Maps vendor payloads to ASIM-aligned canonical schema; deduplicates by correlation ID | `raw-alerts` consumer | `enriched-alerts` |
| **Enrichment Agent** | Adds CMDB asset criticality, identity data, MITRE ATT&CK tags, threat intel IOC status | `enriched-alerts` consumer | `enriched-alerts` (updated) |
| **Orchestrator Agent** | Applies routing rules and risk policy; dispatches to SOAR, Logic Apps, or Functions; enforces approval gate for high-risk actions | `enriched-alerts` consumer | `actions` |
| **Execution Agent** | Executes containment, notification, or remediation with least-privilege identity | `actions` consumer | `audit` |
| **Registry Agent** | Dual-writes `automation.activity` events to Elasticsearch index, Delta Lake, and Sentinel custom table via Log Ingestion API | `audit` consumer | — (terminal sink) |

### 2.3 Canonical Event Schema

Every agent action produces an `automation.activity` event. This schema is the single source of truth for the registry.

```json
{
  "schema_version": "1.0",
  "event_type": "automation.activity",
  "event_id": "<uuid>",
  "correlation_id": "<uuid>",
  "idempotency_key": "<sha256(source_alert_id + action + target_id)>",
  "source_system": "sentinel | splunk",
  "source_workspace_id": "<workspace_id>",
  "source_alert_id": "<alert_id>",
  "source_incident_id": "<incident_id>",
  "playbook_id": "<playbook_name_vX>",
  "playbook_run_id": "<run_uuid>",
  "action": "disable_account | isolate_host | create_ticket | block_ip | ...",
  "target": {
    "type": "user | host | ip | process",
    "id": "<entity_identifier>",
    "asset_criticality": "critical | high | medium | low"
  },
  "status": "queued | executing | succeeded | failed | rejected",
  "approval": {
    "required": true,
    "state": "pending | approved | denied | auto-approved",
    "approver_id": "<entra_object_id>"
  },
  "risk_score": 87,
  "blast_radius": "single-user | subnet | domain",
  "mitre_tactics": ["TA0001", "TA0003"],
  "started_at": "<ISO8601>",
  "ended_at": "<ISO8601>",
  "executor": {
    "type": "agent | logic_app | function",
    "id": "<agent_identity>",
    "managed_identity": "<mi_client_id>"
  },
  "evidence": {
    "input_hash": "sha256:...",
    "raw_alert_ref": "adl://lake/raw/<date>/<event_id>.json",
    "output_ref": "adl://lake/actions/<date>/<run_id>.json"
  },
  "tags": ["severity:high", "env:prod", "bu:finance"]
}
```

### 2.4 Data Flow for Microsoft Sentinel

Microsoft Sentinel supports both data connector-based ingestion for source telemetry and the Log Ingestion API for writing automation records back as custom tables. As of February 2026, Sentinel's data lake tier supports direct ingestion of XDR Advanced Hunting tables without requiring analytics-tier pass-through, enabling cost-effective long-retention storage for raw telemetry. The recommended pattern is:

1. **Source Agent** authenticates via Entra ID app registration and queries the Sentinel Incidents or SecurityAlert tables using KQL via the Logs Query API.
2. Incidents are published to Event Hubs `raw-alerts` topic.
3. After processing, the **Registry Agent** writes `automation.activity` events back to Sentinel using the Log Ingestion API through a Data Collection Rule (DCR) targeting a custom table `SecurityAutomationActivity_CL`.
4. Long-term storage uses the Sentinel Data Lake tier with Delta-format archival (90–730 day retention).

### 2.5 Data Flow for Splunk

Splunk exposes all key data through its REST API and supports alert actions for push delivery. The Splunk SOAR REST API provides programmatic access to containers, incidents, playbooks, and audit records.

1. **Source Agent** issues a scheduled search job via `POST /services/search/jobs`, polls for completion, then pages results from `GET /services/search/jobs/{sid}/results`.
2. Fired alerts are polled from `/services/alerts/fired_alerts`.
3. SOAR audit trail is collected via `GET /rest/audit` filtered by `start` and `end` timestamps.
4. Splunk alert actions (webhook, logevent, summary indexing) can push automation events back into Splunk or forward to the Event Hubs endpoint, enabling closed-loop telemetry without additional polling.

### 2.6 Storage Architecture

| Layer | Technology | Retention | Use Case |
|---|---|---|---|
| Hot search | Elasticsearch / Sentinel custom tables | 30–90 days | Operational dashboards, analyst queries, real-time alerting |
| Warm | Azure Data Lake Gen2 (Parquet) | 90–365 days | Compliance, quarterly review, incident replay |
| Cold / Archive | Azure Data Lake Gen2 (Delta) with lifecycle | 1–7 years | Legal hold, threat hunting at historical scale, ML training |
| Audit | Sentinel `SecurityAutomationActivity_CL` | 90 days hot + lake mirror | Governance, audit reports, SIEM correlation |

Azure Event Hubs supports retention of up to 90 days natively, with Capture enabled to automatically archive all topics to Data Lake Gen2 in Avro or Parquet format. This provides a replay buffer — if a downstream consumer fails, it can catch up from the retained stream rather than requiring re-ingestion from SIEM.

***

## 3. WAF Pillar Assessment

Applying the Azure Well-Architected Framework five pillars to this workload:

| WAF Pillar | Risk | Design Response |
|---|---|---|
| **Reliability** | Source agent failure loses alerts; SOAR downtime halts execution | Event Hubs buffer absorbs bursts; idempotency keys on every action prevent double-execution; dead-letter queue for failed events |
| **Security** | Prompt injection into LLM-based agents; credential leakage; unauthorized action execution | Managed identities only; no stored secrets; sandboxed agent execution environments; approval gate for blast-radius > single entity |
| **Cost Optimization** | SIEM ingestion costs at volume; over-indexing in Elasticsearch | Lake-first for raw logs, analytics tier only for high-value events; tiered Elasticsearch ILM; Event Hubs Standard tier (auto-inflate) for variable load |
| **Operational Excellence** | Agent drift; playbook version drift; observability gaps | Playbook versioning in Git; agent telemetry to Application Insights; every action records playbook ID + version; regular TOGAF Phase H architecture change review |
| **Performance Efficiency** | Alert storm saturation; slow enrichment blocking orchestration | Separate Event Hubs consumer groups per agent role; enrichment cache with TTL; async orchestration with circuit breakers |

***

## 4. TOGAF ADM Mapping

This DTP spans TOGAF ADM Phases A through G:

| ADM Phase | Deliverable in This DTP |
|---|---|
| **A — Architecture Vision** | Section 1: Problem statement, target state, guiding principles |
| **B — Business Architecture** | Section 5: Business unit enablement model, SOC operating model changes |
| **C — Information Systems** | Section 2: Agent catalogue, canonical schema, data flow diagrams |
| **D — Technology Architecture** | Section 2: Component stack, Event Hubs, Data Lake, Elasticsearch, Sentinel integration |
| **E — Opportunities & Solutions** | Section 6: Risk-scored implementation options, build vs. buy decisions |
| **F — Migration Planning** | Section 7: 30-60-90 day phased roadmap with milestones |
| **G — Implementation Governance** | Section 8: Architecture compliance checkpoints, acceptance criteria, RBAC validation |

***

## 5. Business Architecture and Operating Model

### 5.1 Stakeholder Map

| Stakeholder | Interest | Agent Fabric Value |
|---|---|---|
| SOC Analyst (Tier 1/2) | Reduce alert fatigue, understand automated actions | Full action audit trail searchable by incident ID |
| SOC Manager | MTTR metrics, SLA compliance, automation coverage rate | Registry enables KPI dashboards without manual reporting |
| CISO | Governance, compliance, risk posture | Immutable automation log for audit and regulatory inquiry |
| Business Unit (Finance, HR, Operations) | Understand actions taken on their systems | BU-tagged automation events; dashboards per business unit |
| IT / Identity Team | Know when accounts or hosts are automatically changed | Execution events with target entity, approver, and evidence |
| Compliance / Legal | Evidence of controls for SOC 2, ISO 27001, NIS2 | Delta Lake archive with hash-linked provenance |

### 5.2 SOC Operating Model Changes

The agent fabric shifts the SOC from a **reactive playbook-executor** model to a **governed automation overseer** model. Analysts spend less time executing repetitive tier-1 actions and more time reviewing agent decisions, handling escalated approval requests, and tuning agent policies. New roles introduced at business unit enablement (Day 90):

- **Agent Operations Engineer**: monitors agent health, tunes routing rules, manages playbook versioning
- **Automation Steward** (per BU): reviews automation events affecting their domain, approves high-risk actions, reports on automation impact

***

## 6. Build vs. Buy Decisions

| Component | Build | Buy / Native | Recommended |
|---|---|---|---|
| Source Agents | Azure Functions + Sentinel SDK / Splunk SDK | Logic Apps native connectors | **Hybrid**: Logic Apps for Sentinel (native, supported); Python Function for Splunk (more control over paging and auth) |
| Normalizer/Enrichment | Custom Python (full control over ASIM mapping) | Sentinel ASIM parsers | **Build normalizer on ASIM** as the canonical target schema |
| Orchestrator | Custom agent (LLM-assisted routing for complex triage) | Sentinel Automation Rules + Logic Apps | **Hybrid**: rules-based for deterministic routing; LLM agent for ambiguous multi-signal triage |
| SOAR | — | Splunk SOAR (existing PoC) | **Use existing PoC**, extend with audit collection |
| Bus | Kafka (self-managed) | Azure Event Hubs with Kafka endpoint | **Event Hubs** (managed, Kafka-compatible, cost-efficient) |
| Hot Registry | Elasticsearch (self-managed) | Sentinel custom tables (Log Analytics) | **Both**: Sentinel for SIEM-native queries; Elasticsearch for BU-facing search |
| Cold Archive | Custom ETL | Event Hubs Capture → Data Lake Gen2 | **Event Hubs Capture** (zero-code archival) |

***

## 7. Phased Delivery Roadmap

### Phase 1 — Foundation Build (Days 1–30)

**Objective:** Deploy the core ingestion pipeline and registry skeleton. Validate that alerts from Sentinel and Splunk flow through the bus and land in both the hot index and the lake with correct schema.

**Owner:** Engineering (2–3 engineers), Architect lead

#### Week 1–2: Infrastructure and Skeleton

- [ ] Provision Azure Event Hubs namespace (Standard tier, auto-inflate enabled, Kafka endpoint active)
  - Topics: `raw-alerts`, `enriched-alerts`, `actions`, `audit`
  - Retention: 7 days on `raw-alerts`; 1 day on `actions` and `audit`
  - Enable Event Hubs Capture → ADLS Gen2 in Parquet
- [ ] Provision Azure Data Lake Gen2 with lifecycle policies (hot 90d → cool 365d → archive 7yr)
- [ ] Deploy Elasticsearch cluster (Azure Marketplace managed or on-AKS); configure ILM for hot/warm/cold
- [ ] Create Sentinel custom table `SecurityAutomationActivity_CL` via DCR + Log Ingestion API
- [ ] Configure Entra ID app registrations: one per agent with minimum scopes (Sentinel Reader, Log Ingestion, Event Hubs Data Sender/Receiver)
- [ ] Establish Git repository: `agent-fabric/` with CI/CD pipeline (GitHub Actions or Azure DevOps), branch protection, and playbook versioning

#### Week 3–4: Source Agents and Normalizer

- [ ] Deploy **Sentinel Source Agent** (Logic App with timer trigger): query `SecurityIncident` and `SecurityAlert` tables; publish to `raw-alerts`
- [ ] Deploy **Splunk Source Agent** (Python Azure Function): call `/services/search/jobs` for key saved searches; call `/rest/fired_alerts`; publish to `raw-alerts`
- [ ] Deploy **SOAR Audit Agent** (Python Azure Function, 5-minute timer): call Splunk SOAR `/rest/audit` with time-windowed filters; publish to `audit`
- [ ] Deploy **Normalizer Agent**: consume `raw-alerts`; map to canonical ASIM-aligned schema; emit to `enriched-alerts`
- [ ] Deploy **Registry Agent**: consume `audit`; write to Elasticsearch, Sentinel custom table, and Delta Lake
- [ ] **Acceptance Criteria (Day 30 gate):**
  - Sentinel incidents appear in `raw-alerts` within 2 minutes of creation
  - Splunk fired alerts appear within 5 minutes
  - SOAR audit events land in Elasticsearch within 10 minutes
  - Schema validation passes on > 99% of events (dead-letter < 1%)
  - Sentinel custom table queryable via KQL

### Phase 2 — Orchestration Pilot (Days 31–60)

**Objective:** Deploy the enrichment, orchestrator, and execution agents. Operate a controlled pilot with one or two SOC playbooks routed through the fabric. Validate end-to-end audit trail.

**Owner:** Engineering + SOC team

#### Week 5–6: Enrichment and Orchestrator

- [ ] Deploy **Enrichment Agent**: integrate CMDB (ServiceNow or in-house), Entra ID for identity context, and internal threat intel (MDTI or custom); emit enriched events to `enriched-alerts`
- [ ] Deploy **Orchestrator Agent** with routing rule engine:
  - Rules defined in YAML (version-controlled)
  - Risk scoring based on asset criticality × alert severity × blast radius
  - Approval gate: risk score > 70 or blast_radius = domain → queue for human approval
  - Routes to Splunk SOAR for playbook execution; Logic App for direct Azure actions
- [ ] Implement idempotency store (Azure Table Storage or Redis) keyed by `idempotency_key` to prevent duplicate executions
- [ ] Deploy **Execution Agent** stubs for two initial actions: `disable_account` (Entra ID) and `create_ticket` (ServiceNow or Jira)

#### Week 7–8: Pilot and Validation

- [ ] Enable fabric for **two pilot playbooks**: identity compromise triage and phishing email containment
- [ ] Run shadow mode for 1 week (fabric executes but actions require manual confirmation via approval gate) to validate decision quality
- [ ] Switch to auto-approve for low-risk actions (risk score < 40) after shadow validation
- [ ] Dashboard: deploy Kibana/Grafana board connected to Elasticsearch showing action volume, success rate, MTTR, approval queue depth
- [ ] **Acceptance Criteria (Day 60 gate):**
  - End-to-end `automation.activity` event visible in all three registries within 15 minutes of SIEM alert
  - Zero duplicate executions (idempotency verified)
  - Approval gate fires correctly for risk score > 70
  - Playbook version captured in every event
  - Execution agent actions validated by SOC analyst for accuracy

### Phase 3 — Business Unit Enablement and Market Launch (Days 61–90)

**Objective:** Harden, scale, and onboard business units. Deliver governance dashboards, self-service reporting, and executive briefing. Define the operating model and hand off to steady-state operations.

**Owner:** Engineering (hardening) + SOC Manager + BU Leads

#### Week 9–10: Hardening and Security Review

- [ ] Penetration test on agent APIs and Event Hubs endpoints; remediate findings
- [ ] Implement OWASP API Security Top 10 controls on all agent REST surfaces
- [ ] Enable Azure Defender for Storage on Data Lake (malware scanning on action evidence files)
- [ ] Validate RBAC: each agent's managed identity scoped to exactly required permissions; no wildcard roles
- [ ] TOGAF Phase G governance checkpoint: architecture contract review, deviation log, exception register

#### Week 11–12: BU Enablement and Launch

- [ ] Create BU-scoped views in Elasticsearch and Kibana (row-level security by `tags.bu`)
- [ ] Deliver **Automation Registry Portal**: a simple read-only web UI (or Power BI/Grafana dashboard) for BU security stewards to query automation history for their domain
- [ ] Onboard first three business units: Finance, HR, Operations — provide filtered event views and SLA dashboards
- [ ] Define KPIs and baseline them from Day 1 pilot data:
  - Alert-to-action latency (target: < 10 minutes for P1)
  - Automation coverage rate (% of qualifying alerts handled without human tier-1 touch)
  - False positive action rate (actions reversed or overridden by human)
  - Approval queue drain time (target: < 30 minutes for human-required approvals)
- [ ] Executive briefing deck: automation ROI, risk reduction, MTTR improvement vs. pre-fabric baseline
- [ ] **Acceptance Criteria (Day 90 gate — launch):**
  - Three BUs actively consuming automation registry dashboards
  - Governance artifacts complete: RACI, runbook, agent policy YAML, incident response playbook for agent malfunction
  - KPI baseline established and published to CISO
  - Onboarding documentation for additional BUs complete
  - Steady-state operations handed off to Agent Operations Engineer role

***

## 8. Implementation Governance (TOGAF Phase G)

Architecture compliance is enforced at each phase gate through defined acceptance criteria above, plus the following standing controls:

| Control | Mechanism | Frequency |
|---|---|---|
| Schema conformance | Dead-letter queue rate monitored; schema evolution via versioned Avro registry on Event Hubs | Per-deploy |
| Playbook version pinning | Every `automation.activity` event includes `playbook_id` + version; CI/CD gate blocks unversioned deployments | Per-commit |
| RBAC review | Azure Policy audit on managed identity permissions; alerts on privilege escalation | Weekly |
| Architecture change review (TOGAF Phase H) | Architecture change board reviews any new agent, new data source, or action type change | Monthly |
| Audit log integrity | Registry Agent signs each batch with Azure Key Vault before writing to lake | Per-batch |
| BU compliance report | Automated weekly report from registry to BU Automation Steward | Weekly |

***

## 9. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| SIEM API rate limits causing missed alerts | Medium | High | Implement backoff + dead-letter; secondary polling window; Sentinel streaming export as fallback |
| SOAR audit endpoint downtime (Splunk SOAR PoC) | Medium | Medium | Cache last known state; alert on gap detection; fallback to file-based CSV export |
| LLM orchestrator hallucinating wrong routing decision | Low | High | Shadow mode validation before production; rules-based fallback; all LLM decisions logged with confidence score |
| Event Hubs consumer lag under alert storm | Medium | Medium | Auto-inflate, dedicated premium tier namespace for P1 alerts; separate partition per alert severity |
| Duplicate action execution during agent restart | Medium | High | Idempotency key store with 24-hour TTL; check-before-act pattern in Execution Agent |
| BU over-reliance on automation, reduced human vigilance | Low | High | Monthly human review of auto-approved action sample; false positive rate KPI threshold triggers manual review mode |

***

## 10. Technology Stack Summary

| Layer | Component | Version / Tier | Notes |
|---|---|---|---|
| SIEM Source | Microsoft Sentinel | Current GA (Defender portal) | Log Ingestion API for write-back |
| SIEM Source | Splunk Enterprise | Current PoC | REST API search/jobs + fired_alerts |
| SOAR | Splunk SOAR | Current PoC | REST `/rest/audit`, `/rest/playbook`, `/rest/container` |
| Agent Runtime | Azure Functions (Python 3.11) | Consumption / EP1 | Stateless, managed identity auth |
| Logic Apps | Standard tier | Stateful workflows | Sentinel native connectors |
| Bus | Azure Event Hubs | Standard (Kafka endpoint) | Auto-inflate, Capture enabled |
| Hot Registry | Elasticsearch 8.x | Azure managed or AKS | ILM policy; Kibana for dashboards |
| Warm/Cold Registry | Azure Data Lake Gen2 | LRS + lifecycle | Event Hubs Capture → Parquet/Delta |
| Audit Registry | Sentinel Custom Table | Log Analytics | `SecurityAutomationActivity_CL` via DCR |
| Identity | Entra ID Managed Identities | — | No stored secrets; per-agent registration |
| Secret Store | Azure Key Vault | Standard | Audit log signing keys; API tokens for non-MI systems |
| Observability | Azure Monitor + App Insights | — | Agent health, consumer lag, dead-letter rates |
| CI/CD | GitHub Actions / Azure DevOps | — | Branch protection; playbook version gate |

***

## 11. Immediate Next Steps (Days 1–7)

1. **Architecture contract sign-off**: CISO, SOC Manager, and Architecture Review Board approve this DTP and confirm the target stack
2. **Provision core infrastructure**: Event Hubs namespace, ADLS Gen2, Key Vault, Entra app registrations (1 day with IaC via Bicep or Terraform)
3. **Assign roles**: Agent Ops Engineer (or designated engineer), BU Automation Steward nominees (Finance, HR, Operations)
4. **Sentinel connector inventory**: audit existing data connectors and identify which tables will feed the Source Agent; confirm Log Ingestion API access
5. **Splunk REST API access**: validate API token generation, firewall rules, and rate limit quotas for the Splunk Source Agent
6. **Splunk SOAR audit trail**: enable audit tracking for Containers, Playbooks, and Users in SOAR Administration > System Health > Audit Trail
7. **Define YAML routing rules v0**: SOC team drafts initial playbook routing policy for pilot (two use cases: identity compromise, phishing)
