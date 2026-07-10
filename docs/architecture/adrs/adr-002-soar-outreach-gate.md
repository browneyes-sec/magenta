# ADR-002: SOAR Outreach Gate Architecture

## Status
Accepted

## Context
The platform requires bidirectional SOAR integration: Magenta agents must both push decisions into Splunk SOAR (creating containers, triggering playbooks) and pull audit/execution results back. The assessment found no Splunk SOAR connector existed — the `integration/` directory only had Sentinel, Splunk Enterprise, Entra, and Defender connectors.

The SOAR outreach gate must support 8 operations:
- Container lifecycle: get, create, update
- Playbook dispatch: trigger, poll runs
- Audit trail collection
- Note posting
- Action run history

## Decision
Create a dedicated `SOARConnector` class in `magenta/integration/soar.py` with an 8-method interface, session key caching with TTL check, and circuit breaker protection. A `SOARDispatcher` in `orchestration/dispatcher.py` orchestrates the full lifecycle: resolve playbook → create container → trigger playbook → poll status → register state transitions.

The dispatch flow is:
1. Resolve playbook name from `config/routing-rules.yaml`
2. `soar.create_container()` with enriched alert + `automation_source:magenta` metadata
3. `soar.post_note()` with agent reasoning
4. `soar.trigger_playbook()` with resolved playbook name
5. Async polling via `soar.get_playbook_runs()` every 10s for 5 minutes
6. Each state transition emitted as `automation.activity` to the registry

## Rationale
- **Dedicated connector** keeps SOAR concerns isolated from the generic Splunk connector
- **Session TTL caching** prevents mid-operation auth failures during long-running playbooks
- **Circuit breaker** prevents SOAR API downtime from cascading to agent pipeline
- **Routing rules YAML** decouples playbook selection from code
- **Async polling** enables non-blocking SOAR dispatch: agents continue working while playbook runs

## Consequences
- Positive: SOAR is now a first-class integration target with full lifecycle management
- Positive: Routing rules can be updated without code changes
- Trade-off: 5-minute max poll time is adequate for most playbooks but long-running playbooks (>30 min) may need external reconciliation
- Risk: SOAR API rate limits could cause backoff cascade; mitigated by circuit breaker + exponential backoff

## Compliance
- All SOAR API calls go through `_request()` (circuit breaker wrapper)
- Containers always include `automation_source:magenta` and `correlation_id` tags
- Every SOAR dispatch state transition is registered as `automation.activity`
