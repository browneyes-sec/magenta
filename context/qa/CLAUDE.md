# QA Agent Context — Magenta

## Domain Overview

QA ensures the reliability, correctness, and security of the agent fabric. This includes unit/integration tests, chaos engineering, schema validation, idempotency verification, and acceptance criteria enforcement at each phase gate.

## Technology Stack

- **Framework:** pytest (Python agents), Jest / Playwright (frontend)
- **Integration:** Azure Functions test harness, Event Hubs emulator, Elasticsearch test containers
- **Chaos engineering:** Azure Chaos Studio or custom fault injection
- **Coverage:** 90%+ line coverage target; 100% on approval gate and idempotency logic
- **Performance:** Locust or k6 for load testing Event Hubs consumer patterns

## Testing Strategy

| Tier | Scope | Tool | Frequency |
|---|---|---|---|
| Unit | Individual agent logic | pytest | Every commit |
| Integration | Agent-to-topic data flow (end-to-end) | Test containers | Every PR |
| Schema | Avro schema conformance | Custom schema validator | Every deploy |
| Idempotency | Duplicate prevention verification | pytest + mock idempotency store | Every PR |
| Chaos | Consumer lag, circuit breaker, dead-letter | Chaos Studio / fault injection | Weekly |
| Performance | Alert storm saturation | k6 / Locust | Pre-release |
| Security | RBAC scoping, secret exposure | OWASP ZAP / Bandit | Every PR |

## Conventions

- **Test data:** Use factory fixtures; never depend on production data
- **Fixtures:** Every test that touches Event Hubs uses a mock producer/consumer
- **Naming:** `test_<agent>_<scenario>_<expected_outcome>.py`
- **Assertions:** Always assert on event schema fields, not just HTTP status codes

## Guardrails

- NEVER skip tests by commenting them out — use `@pytest.mark.skipif` with explicit reason
- NEVER commit tests that depend on hardcoded tenant IDs or workspace IDs
- NEVER run load tests against production Event Hubs without Ops approval
- ALWAYS verify `idempotency_key` uniqueness under concurrent execution
- ALWAYS include at least one schema validation failure test per agent
- ALWAYS test approval gate at boundary values (risk_score 69, 70, 71; blast_radius transitions)
- ALWAYS test dead-letter path — every agent must handle unrecoverable events gracefully

## Cross-Domain Interfaces

| Domain | Interface | Protocol |
|---|---|---|
| Backend | Provide agent test fixtures | pytest fixtures |
| Data | Validate schema conformance in test pipeline | Avro schema registry |
| Frontend | Validate dashboard accuracy | Playwright + seeded data |
| Ops | Gate deployments on test results | CI/CD pipeline |
| Ops | Report test coverage and flaky tests | Test analytics dashboard |

## Feedback Loops

- Flaky tests are quarantined automatically after 3 failures and assigned to the owning domain
- Acceptance criteria at each phase gate (Day 30, 60, 90) are codified as automated integration tests
- Chaos engineering results published as a weekly reliability scorecard
