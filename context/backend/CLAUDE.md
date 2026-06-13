# Backend Agent Context — Magenta

## Domain Overview

Backend agents implement the core event-driven pipeline: source ingestion, normalization, enrichment, orchestration, execution, and registry writing. All agents run as stateless Azure Functions (Python 3.11) or Logic Apps.

## Technology Stack

- **Runtime:** Azure Functions (Python 3.11, Consumption/EP1 plan)
- **Stateful workflows:** Logic Apps Standard
- **Messaging:** Azure Event Hubs (Kafka endpoint)
- **Identity:** Entra ID Managed Identities (per-agent)
- **Secrets:** Azure Key Vault
- **Storage:** Azure Table Storage / Redis (idempotency)
- **CI/CD:** GitHub Actions / Azure DevOps

## Architecture

All agents follow the same pattern:
1. **Trigger** — timer, Event Hubs message, or webhook
2. **Process** — transform/enrich/route with idempotency check
3. **Emit** — publish result to next Event Hubs topic
4. **Log** — structured telemetry to Application Insights

## Conventions

- **Language:** Python 3.11 with type hints on all public functions
- **Testing:** pytest with fixtures for Event Hubs mock; 90%+ coverage target
- **Logging:** structured JSON logs via Application Insights; no print/console.log
- **Error handling:** circuit breakers for downstream dependencies; dead-letter on unrecoverable failures
- **Idempotency:** check idempotency store before every action execution
- **Schema validation:** Avro schema registry on Event Hubs; validate on produce and consume

## Guardrails

- NEVER hardcode credentials, connection strings, or tenant IDs — use managed identities or Key Vault references
- NEVER commit `.env`, `local.settings.json`, or `__pycache__/`
- NEVER use wildcard RBAC roles (`Contributor`, `Owner`) — scope to minimum required actions
- NEVER bypass the idempotency check — duplicate executions are unacceptable
- NEVER log raw secrets, tokens, or PII in Application Insights
- ALWAYS include `playbook_id` and `playbook_version` in every emitted event
- ALWAYS set `Content-Type: application/json` with Avro-validated payloads
- ALWAYS handle Event Hubs consumer lag — implement backpressure and alert if lag > 1000 messages

## Cross-Domain Interfaces

| Domain | Interface | Protocol |
|---|---|---|
| Data | Emit to `enriched-alerts`, `actions`, `audit` topics | Event Hubs (Avro) |
| Data | Consume `raw-alerts`, `audit` topics | Event Hubs (Avro) |
| Ops | Export telemetry to Application Insights | OpenTelemetry / Azure Monitor |
| Ops | Deploy via CI/CD pipeline | GitHub Actions / Azure DevOps |
| QA | Supply test fixtures for integration tests | pytest fixtures |

## Feedback Loops

- Every PR must include: unit tests, updated schema validation, and a dead-letter handling strategy
- All agent function signatures must be documented with docstrings
- Approval gate logic must have explicit test coverage for edge cases (risk score boundaries, blast radius extremes)
