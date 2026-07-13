# Architecture Change Request (ACR) Process

## Overview
This document defines the process for proposing, reviewing, and implementing architecture changes in the Magenta ASOAR platform per TOGAF ADM Phase H.

## When to Submit an ACR
An ACR is required for any change that triggers one of the following (per DTP-03 §4.1):

1. New agent role added to the registry
2. New action type with `blast_radius > subnet`
3. New external data source (new SIEM, new threat intel feed)
4. Schema change to `AutomationActivity` canonical model
5. New LLM provider or model tier
6. Infrastructure topology change (new Azure region, new K8s node pool)
7. Any WAF pillar score drops below 3/5 in quarterly assessment

## ACR Lifecycle

### 1. Draft (Requester)
- Create ACR from template: `architecture/ACR/ACR-NNN-template.md`
- Fill all sections including Impact Assessment
- Submit PR to `architecture/ACR/` with label `acr:draft`

### 2. Triage (Architecture Board Chair)
- Within 2 business days: assign ACR number, validate completeness
- If incomplete: return to requester with comments
- If complete: label `acr:triage`, schedule for next Board meeting

### 3. Review (Architecture Board)
- Board meets monthly (first Tuesday, 30 min)
- Review impact assessment, WAF pillar scores, security implications
- Decision: **Approved**, **Approved with Conditions**, **Deferred**, **Rejected**
- Record decision in ACR file under `## Decision`

### 4. Implementation (Requester + Team)
- If approved: create implementation PR(s) referencing ACR-NNN
- Update DTP, CI gates, Architecture Contract as needed
- Add monitoring/alerts for new component
- Run chaos test if new failure mode introduced

### 5. Closure (Architecture Board)
- Verify implementation matches approved design
- Update ACR status to `Implemented`
- Archive ACR after 90 days

## Emergency Changes
For production incidents requiring immediate architecture change:
1. On-call engineer implements fix with minimal scope
2. Create ACR within 24 hours (retroactive)
3. Emergency Board review within 48 hours
4. Document in Deviation Log (`architecture/DEVIATION_LOG.md`)

## Change Board Composition
| Role | Representative | Voting |
|------|---------------|--------|
| Architecture Board Chair | Senior Integrations Engineer | Yes |
| Enterprise Architect | Rotating Board Member | Yes |
| Security | SOC Manager | Yes (security changes) |
| Business Unit | BU Rep (rotating) | Yes (blast_radius=enterprise) |
| Platform | Ops Lead | Advisory |

## Quorum
Minimum 3 voting members including Chair. Security changes require SOC Manager.

## Artifacts Updated on Approval
- [ ] Relevant DTP section(s)
- [ ] `.github/workflows/architecture-compliance.yml` (if new gate needed)
- [ ] Architecture Contract (AC-01 through AC-04)
- [ ] Prometheus rules / Grafana dashboards
- [ ] Runbooks (if new component)
- [ ] ADR (if new architectural decision)

## Schema Change Management
For `AutomationActivity` schema changes (Category: Schema Change):

| Change Type | Policy | Process |
|------------|--------|---------|
| New optional field | Non-breaking — allowed | ADR update + schema registry update |
| New required field | Breaking — requires migration | ACR + consumer migration plan |
| Field rename/delete | Breaking — prohibited without deprecation | 2-sprint deprecation window |
| Enum value added | Non-breaking | ADR update |
| Enum value removed | Breaking | ACR + consumer audit |

Schema version in `AutomationActivity.schema_version` must be incremented on breaking changes.

## References
- DTP-03 §4 (TOGAF Phase H)
- DTP-03 §6 (AC-03 Acceptance Criteria 3.8)
- `architecture/DEVIATION_LOG.md`