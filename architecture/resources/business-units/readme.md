# Business Unit Architecture

## Component Overview

Magenta's multi-tenant model enables business units (Finance, HR, Operations, etc.) to view automation actions affecting their systems while preserving global SOC visibility. Every `automation.activity` event carries BU context via the `tags.bu` field.

DTP references: §5.1 (Stakeholder Map), §5.2 (SOC Operating Model), §7.3 (BU Enablement), §8 (Governance)

## BU Tagging Strategy

```yaml
# config/business-units.yaml
business_units:
  finance:
    id: bu-finance
    tags: ["bu:finance", "env:prod"]
    asset_criticality_default: high
    data_classification: restricted
    automation_steward: ["alice@contoso.com"]
    notification_channel: "#bu-finance-security"

  hr:
    id: bu-hr
    tags: ["bu:hr", "env:prod"]
    asset_criticality_default: high
    data_classification: confidential
    automation_steward: ["bob@contoso.com"]

  operations:
    id: bu-ops
    tags: ["bu:ops", "env:prod"]
    asset_criticality_default: medium
    data_classification: internal
    automation_steward: ["carol@contoso.com"]

  shared:
    id: bu-shared
    tags: ["bu:shared"]
    asset_criticality_default: low
    data_classification: public
    automation_steward: []  # SOC-managed
```

BU assignment can happen at multiple levels:

| Level | Mechanism | Example |
|---|---|---|
| Target asset | CMDB attribute | `target.id` resolved to `domain: finance.contoso.com` → `bu:finance` |
| Source alert tag | SIEM rule metadata | Sentinel incident tagged `bu:hr` |
| IP range | Subnet lookup | `10.0.0.0/16` → `bu:ops` |
| Manual override | API header | `X-Business-Unit: finance` on webhook |

### Tag Resolution Logic

```python
class BusinessUnitResolver:
    def __init__(self):
        self._ranges = {
            "10.0.0.0/16": "bu-ops",
            "10.1.0.0/16": "bu-finance",
            "10.2.0.0/16": "bu-hr",
        }

    async def resolve(self, alert: dict) -> list[str]:
        tags = []
        # 1. Check source tags
        source_tags = alert.get("tags", [])
        tags.extend(t for t in source_tags if t.startswith("bu:"))

        # 2. Check target IP/hostname
        target = alert.get("target", {})
        if target.get("type") == "ip":
            for cidr, bu in self._ranges.items():
                if ip_address(target["id"]) in ip_network(cidr):
                    tags.append(bu)
                    break

        # 3. Default
        if not tags:
            tags.append("bu:shared")

        return tags
```

## Row-Level Security (Elasticsearch)

Each Elasticsearch index applies document-level security based on BU tags:

```json
{
  "query": {
    "bool": {
      "filter": [
        {
          "terms": {
            "tags": ["bu:finance", "bu:shared"]
          }
        }
      ]
    }
  }
}
```

Kibana spaces per BU:

```yaml
elasticsearch:
  kibana_spaces:
    bu-finance:
      index_patterns: ["magenta-*"]
      document_level_security:
        - tags: "bu:finance"
    bu-hr:
      index_patterns: ["magenta-*"]
      document_level_security:
        - tags: "bu:hr"
    soc-global:
      index_patterns: ["magenta-*"]
      document_level_security:
        - tags: "*"
```

## BU Dashboard (Elasticsearch / Kibana / Power BI)

```python
# Conceptual: BU dashboard query
async def get_bu_dashboard(bu_id: str, days: int = 30) -> dict:
    query = {
        "size": 0,
        "query": {"bool": {"filter": {"terms": {"tags": [bu_id]}}}},
        "aggs": {
            "actions_over_time": {"date_histogram": {"field": "started_at", "calendar_interval": "day"}},
            "by_status": {"terms": {"field": "status"}},
            "by_action": {"terms": {"field": "action"}},
            "avg_risk_score": {"avg": {"field": "risk_score"}},
            "top_affected_assets": {"terms": {"field": "target.id", "size": 10}},
        },
    }
    return await elastic_client.search("automation-activity", query)
```

### Dashboard Widgets

| Widget | Data Source | BU Stakeholder |
|---|---|---|
| Actions affecting us (last 30 days) | ES aggregation | Automation Steward |
| Action success/fail rate | ES aggregation | Automation Steward |
| Risk score distribution | ES aggregation | BU Security Owner |
| Top affected assets | ES aggregation | IT Operations |
| MTTR (mean time to resolve) | ES aggregation | SOC Manager |
| Approval requests I need to review | Redis + WebSocket | Automation Steward |
| Pending approvals (SLA timer) | Redis | Automation Steward |

## Automation Steward Role

Introduced at Day 90 BU enablement (DTP §5.2):

```yaml
automation_steward:
  responsibilities:
    - Review weekly automation activity for their BU
    - Approve/reject high-risk actions affecting their domain
    - Maintain BU asset criticality and data classification
    - Escalate automation anomalies to SOC
  permissions:
    - missions:read (scoped to BU)
    - approval:high-risk (scoped to BU)
    - reports:read (scoped to BU)
  training:
    - Magenta BU Steward onboarding (30 min)
    - Approval workflow walkthrough
    - Incident response for agent malfunction
```

## BU Onboarding Playbook

```markdown
## Onboarding New Business Unit

### Prerequisites
- [ ] BU stakeholder identified (Automation Steward nominee)
- [ ] Asset inventory with criticality classification
- [ ] IP ranges / domains / tenant IDs mapped to BU
- [ ] Notification channel (Slack/Teams/email)

### Steps
1. Add BU to `config/business-units.yaml`
2. Deploy configuration change via CI/CD
3. Create Elasticsearch role + Kibana space for BU
4. Configure row-level security filter
5. Validate: trigger a test alert with BU tag, verify dashboard shows it
6. Schedule training session for Automation Steward
7. Grant permissions (missions:read, approval:high-risk scoped to BU)
8. Enable BU notification channel

### Estimated Effort
- Technical setup: 2 hours
- Stakeholder training: 30 min
- Validation period: 2 days (shadow mode)
```

## BU Isolation Matrix

| Data Type | SOC (Global) | BU Steward | BU Read-Only |
|---|---|---|---|
| All missions | Full access | Scoped to BU | Scoped to BU (read) |
| Agent decisions | Full access | Scoped to BU | Scoped to BU (read) |
| Action outcomes | Full access | Scoped to BU | Scoped to BU (read) |
| Approval requests | Full access | Scoped to BU | None |
| Risk scores | Full access | Scoped to BU | Aggregated only |
| Cross-BU data | Full access | Denied | Denied |
| Configuration | Full access | Denied | Denied |
| Agent logs | Full access | Denied | Denied |

## Monitoring

| Metric | Alert |
|---|---|
| BU with no activity > 7 days | Info — check connector health |
| Unclassified alerts (no BU tag) > 5% | Warning — update resolution rules |
| BU dashboard query failure > 1% | Warning |
| Automation Steward approval SLA breached | Warning |
| Cross-BU data access attempt > 0 | Investigate (RBAC violation) |
