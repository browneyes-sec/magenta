# Management User Guide

## Audience

CISOs, SOC managers, compliance officers, and IT leadership evaluating, deploying, and governing the Magenta ASOAR framework.

## Table of Contents

1. [Overview for Decision Makers](#overview-for-decision-makers)
2. [Capability Matrix](#capability-matrix)
3. [Governance & Compliance](#governance--compliance)
4. [Cost Analysis](#cost-analysis)
5. [Metrics & Reporting](#metrics--reporting)
6. [Teaming Structure Selection Guide](#teaming-structure-selection-guide)
7. [Risk & Escalation Policies](#risk--escalation-policies)

---

## Overview for Decision Makers

Magenta is an **open-weight, LLM-agnostic multi-agent framework** for cybersecurity SOAR operations. It replaces rigid playbook-based automation with intelligent agent swarms that collaborate like human SOC teams.

### Key Business Benefits

| Benefit | Impact |
|---|---|
| **Reduce MTTD/MTTR** | AI agents triage and respond in seconds, not minutes |
| **Lower operational cost** | Open-weight models (OLLAMA) — no per-seat LLM licensing |
| **Audit-ready compliance** | Immutable `automation.activity` registry for every decision |
| **Vendor independence** | LLM-agnostic — swap models without changing workflows |
| **Human-in-the-loop** | Risk-graded escalation ensures judgment overrides when needed |
| **Scalable SOC operations** | Handle alert surges with elastic agent pools |

### When to Use Magenta

| Good Fit | Poor Fit |
|---|---|
| High-volume alert triage (>50/day) | Simple pass/fail automation (use basic SOAR) |
| Complex multi-step investigations | Environments requiring no AI/ML |
| Regulatory compliance (SOC2, PCI-DSS, HIPAA) | Air-gapped networks without OLLAMA |
| Heterogeneous SIEM environment (Sentinel + Splunk) | Single-alert-source environments |
| Need for auditable decision trails | Budget for commercial SOAR with LLM included |

## Governance & Compliance

### Audit Trail

Every agent decision is written to three locations:

1. **Elasticsearch** (`automation-activity` index) — hot query for current investigations
2. **Azure Data Lake / S3** — cold storage for long-term retention
3. **SIEM Custom Tables** (Sentinel, Splunk) — unified with source alerts

```json
{
  "event_type": "automation.activity",
  "event_id": "uuid",
  "correlation_id": "uuid",
  "source_alert_id": "sentinel-incident-8932",
  "action": "isolate_host",
  "status": "succeeded",
  "risk_score": 72,
  "executor": {
    "type": "agent",
    "id": "contain-01"
  },
  "evidence": {
    "input_hash": "sha256...",
    "raw_alert_ref": "sentinel/incidents/8932"
  }
}
```

### Compliance Frameworks

| Framework | Magenta Support |
|---|---|
| SOC 2 (Trust Services Criteria) | Activity logging, access controls, change management |
| PCI-DSS v4.0 | Requirement 10 (audit trails), Requirement 7 (access control) |
| HIPAA Security Rule | §164.312(b) audit controls, §164.308(a)(1)(ii)(D) information access |
| NIST 800-53 | AU family (audit and accountability), AC family (access control) |
| NIST CSF 2.0 | DE (detect), RS (respond), RC (recover) functions |

### RBAC Model

```yaml
roles:
  soc_analyst:
    permissions: [missions:read, approval:low-risk]
    scope: assigned_team_only
  soc_engineer:
    permissions: [missions:*, playbooks:*, agents:read]
    scope: entire_org
  soc_admin:
    permissions: [*]
    scope: entire_org
  soc_manager:
    permissions: [missions:read, approval:*, reports:read]
    scope: entire_org
  auditor:
    permissions: [activity:read, reports:read]
    scope: entire_org
```

## Cost Analysis

### Total Cost of Ownership (TCO) Estimate

| Component | Monthly Cost (estimate) |
|---|---|
| **Compute (3-node K8s cluster)** | $300-600 (Azure AKS / AWS EKS) |
| **GPU (1× A100 or 2× RTX 4090)** | $500-2,000 (on-demand) or $200-800 (spot) |
| **Storage (Elasticsearch + Data Lake)** | $100-300 |
| **SIEM ingestion (Sentinel, Splunk)** | Existing SIEM budget |
| **API costs (Gemini, Groq — optional)** | $0-50 (free tier sufficient for most) |
| **OLLAMA licensing** | $0 (open-source) |
| **Magenta licensing** | $0 (open-source, Apache 2.0) |
| **Estimated Total** | **$900-3,000/month** |

### Cost Comparison: Magenta vs. Commercial SOAR + LLM

| Factor | Commercial SOAR + LLM | Magenta Framework |
|---|---|---|
| License cost | $50-150/GB/day ingestion | $0 (Apache 2.0) |
| LLM cost | $0.01-0.03 per API call | $0 (OLLAMA local) |
| Infrastructure | Vendor-managed cloud | Self-managed (K8s/VM) |
| Vendor lock-in | Proprietary playbooks | Open-source, LLM-agnostic |
| Audit data access | Portal-only | Full Elasticsearch/SQL access |

## Metrics & Reporting

### Key Performance Indicators

| Metric | Target | Measurement |
|---|---|---|
| Mean Time to Triage | < 30 seconds | Alert → triage agent assignment |
| Mean Time to Contain | < 5 minutes | Alert → containment action |
| Mean Time to Report | < 15 minutes | Alert → final report |
| Agent accuracy | > 90% | Human-review pass rate |
| False positive reduction | > 40% | Alerts auto-resolved without human touch |
| Approval SLA | < 5 minutes | Pending → approved/rejected |
| Uptime | > 99.9% | API health endpoint |

### Dashboard View (Example)

```
MAGENTA — SOC DASHBOARD                Last 24 hours
─────────────────────────────────────────────────────
Alerts received:         247
Missions created:        247
Auto-resolved:           103  (42%)
Agent-reviewed:          97   (39%)
Human-led:               47   (19%)

Average MTTD:           18s
Average MTTR:           3m 42s
Agent accuracy:         94.2%

Pending approvals:      3
Active missions:        12
Failed missions:        1    (0.4%)

Infrastructure:
  API uptime:           99.98%
  OLLAMA availability:  100%
  ES cluster health:    green
```

### Generating Management Reports

```bash
# CLI report for last 7 days
magenta orchestrate list --format json | \
    python3 -c "
import sys, json
missions = json.load(sys.stdin)
total = len(missions)
auto = sum(1 for m in missions if m.get('auto_resolved'))
print(f'Total: {total}, Auto-resolved: {auto} ({auto/total*100:.0f}%)')
"
```

## Teaming Structure Selection Guide

| Structure | Best For | Example Scenario | Management Notes |
|---|---|---|---|
| **Supervisor** | Complex multi-step incidents | Ransomware response (triage → enrich → contain → investigate → report) | Highest audit detail; monitor agent depth |
| **Debate** | False positive reduction | Phishing alert — 3 agents vote on verdict | Reduces analyst fatigue; set consensus threshold |
| **Pipeline** | Standard playbooks | User account compromise (disable → reset → notify) | Most predictable; easiest to SLA |
| **Mesh** | High-volume surges | 100+ low-severity alerts in 5 minutes | Best for burst handling; requires over-provisioned agent pool |
| **Referee** | High-risk actions | Domain admin account disable | For compliance-sensitive environments |

## Risk & Escalation Policies

### Default Escalation Matrix

| Risk Score | Auto-Approved? | Requires Approval? | Notify SOC Manager? |
|---|---|---|---|
| 0-30 | Yes | No | No |
| 31-50 | Yes | No | If > 3 in 1 hour |
| 51-70 | No | SOC Analyst | If pending > 10 min |
| 71-85 | No | SOC Manager | Yes |
| 86-100 | No | Emergency approval | Yes, immediately |

### Customizing Risk Policies

```yaml
# config/risk-policies.yaml
risk_policies:
  - action: isolate_host
    base_risk: 50
    modifiers:
      - condition: target.criticality == "critical"
        add: 30
      - condition: blast_radius == "domain"
        add: 15
      - condition: "confirmed_malware"
        add: 20
    max_auto_approve: 60
  - action: disable_account
    base_risk: 30
    modifiers:
      - condition: target.role == "admin"
        add: 40
    max_auto_approve: 50
```

## Getting Started — Management Checklist

- [ ] Review the [Architecture Resources](../../architecture/resources/readme.md) for infrastructure sizing
- [ ] Define risk tolerance thresholds for each action type
- [ ] Select teaming structure(s) for your alert categories
- [ ] Configure RBAC roles (Soc Analyst, SOC Manager, Auditor)
- [ ] Set up monitoring dashboards for KPI tracking
- [ ] Define compliance reporting cadence (daily/weekly/monthly)
- [ ] Train analysts on approval workflows and mission monitoring
