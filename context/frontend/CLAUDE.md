# Frontend Agent Context — Magenta

## Domain Overview

The frontend domain delivers the **Automation Registry Portal** — a read-only web UI for BU security stewards to query automation history, plus dashboards (Kibana/Grafana/Power BI) for SOC operations.

## Technology Stack

- **Primary UI:** Read-only web portal (React or lightweight framework)
- **Dashboards:** Kibana (Elasticsearch) · Grafana · Power BI
- **Data source:** Elasticsearch (hot registry) · Sentinel Log Analytics (audit)
- **Auth:** Entra ID SSO (delegated user permissions, row-level security by `tags.bu`)
- **Deployment:** Static site + API gateway · Azure Static Web Apps or similar

## Conventions

- **UI framework:** Prefer minimal dependencies — no heavy component libraries for a read-only portal
- **State management:** Server-driven — data comes from Elasticsearch; no local state complexity
- **Query layer:** REST API proxy that enforces row-level security (RLS) by user's BU claim
- **Dashboards:** Infrastructure-as-code — Kibana saved objects / Grafana dashboards versioned in Git
- **Accessibility:** WCAG 2.1 AA minimum

## Guardrails

- NEVER embed Elasticsearch credentials or API keys in frontend code — proxy all queries through a backend-for-frontend (BFF)
- NEVER expose raw internal schemas to the UI — always use a view layer that maps fields to BU-friendly labels
- NEVER mutate data — the portal is read-only; all writes happen through backend agents
- NEVER render raw HTML from Elasticsearch documents — sanitize all text fields
- ALWAYS scope dashboards by `tags.bu` — BU stewards must only see events tagged to their business unit
- ALWAYS display the `approval.state` and `status` fields prominently on every action detail view
- ALWAYS include a human-readable timestamp with timezone in every table and detail view

## Cross-Domain Interfaces

| Domain | Interface | Protocol |
|---|---|---|
| Data | Read from Elasticsearch indices `automation-activity-*` | REST API |
| Data | Read from Sentinel `SecurityAutomationActivity_CL` (KQL) | Log Analytics API |
| Backend | Actions emit to `audit` topic consumed by Registry Agent | Event Hubs |
| Ops | Deploy dashboard configuration through CI/CD | GitHub Actions / Azure DevOps |
| QA | Validate dashboard data accuracy against test events | Cypress / Playwright |

## Feedback Loops

- BU stewards can flag incorrect or missing data — flag creates a support ticket with `correlation_id`
- Dashboard load time must be < 3 seconds for a 30-day window (Elasticsearch performance baseline)
- Weekly compliance report sent to BU Automation Steward from registry data
