# ACR-NNN: [Change Title]

**Submitted:** YYYY-MM-DD
**Requester:** [Name/Role]
**Category:** New Agent | New Data Source | New Action | Schema Change | Infrastructure

## Change Description
[What is changing and why]

## Impact Assessment
| Dimension | Impact | Detail |
|-----------|--------|--------|
| Event schema | Breaking / Non-breaking | [Fields added/removed] |
| Affected topics | [EH topics] | [Consumer groups affected] |
| WAF pillar impact | [Pillar name] | [Score change expected] |
| Security | Low / Medium / High | [Auth, RBAC, network impact] |
| Blast radius change | [If new action type] | [New max blast_radius] |

## ADR Required
[ ] Yes — create ADR-NNN: [title]
[ ] No — change is within existing architectural bounds

## Approval
- [ ] Architecture Board Chair (required)
- [ ] SOC Manager (required if security impact)
- [ ] BU Representative (required if blast_radius = enterprise)

## Rollback Plan
[Steps to revert if change causes incidents]

## Phase Gate
[ ] DTP updated
[ ] CI compliance gate updated
[ ] Acceptance criteria added to Architecture Contract
[ ] Monitoring/alert updated for new component