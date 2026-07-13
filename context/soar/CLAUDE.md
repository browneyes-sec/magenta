# SOAR Integration Agent Context

## Domain
Splunk SOAR REST API integration, playbook dispatch, container lifecycle, audit collection, outreach gate.

## Technology Stack
- **Integration:** `magenta/integration/soar.py` — SOAR REST API connector
- **Dispatch:** `magenta/orchestration/dispatcher.py` — SOARDispatcher
- **Routing:** `config/routing-rules.yaml` — playbook routing rules
- **Events:** `automation.activity` canonical schema via EventHub/Registry

## Architecture: SOAR Outreach Gate

```
Magenta Orchestrator
    │
    ├──► SOAR Outreach Gate (soar.py + SOARDispatcher)
    │         │
    │         ├── push: create_container() → Splunk SOAR Container
    │         ├── push: trigger_playbook() → SOAR Playbook Execution
    │         └── pull: get_audit_trail()  → automation.activity events
    │
    └──► Registry Agent (via audit topic)
              │
              ├── Elasticsearch hot index
              ├── Sentinel SecurityAutomationActivity_CL
              └── Azure Data Lake Delta partition
```

## Authentication

- **Method:** Token-based via `POST /services/auth/login`
- **Caching:** Session key cached with 5-minute buffer before 24h expiry
- **Refresh:** Auto-refresh on 401 responses via `_login()` TTL check
- **Security:** `verify=True` always — never `verify=False` in non-dev environments

## Container Lifecycle

```
States: new → open → in_progress → resolved | closed
```

All containers created by Magenta agents must include:
- `automation_source: magenta` (set automatically)
- `correlation_id` in tags for end-to-end tracing
- `playbook_id` and `playbook_version` for change management

## Playbook Dispatch Rules

### Pre-Dispatch Validation
1. Container ID must be valid before calling `trigger_playbook()`
2. Never re-trigger a running playbook — check `get_playbook_runs()` first
3. Playbook names resolved from `config/routing-rules.yaml`, not hardcoded

### Dispatch Flow
1. `create_container()` with enriched alert context
2. `post_note()` with agent reasoning and decision rationale
3. `trigger_playbook()` with resolved playbook name
4. Async polling via `get_playbook_runs()` for state transitions
5. Each state transition emits `automation.activity` to registry

### State Transition Events
| Transition | Action Field | Status |
|-----------|-------------|--------|
| Container created | `soar_container_created` | `queued` |
| Playbook triggered | `soar_playbook_triggered` | `executing` |
| Playbook succeeded | `soar_playbook_succeeded` | `succeeded` |
| Playbook failed | `soar_playbook_failed` | `failed` |
| Container resolved | `soar_container_resolved` | `succeeded` |

## Audit Collection

### Window Configuration
- **Period:** 5-minute sliding window (never use absolute timestamps)
- **API:** `get_audit_trail(start, end)` with timezone-aware ISO 8601 timestamps
- **Offset Awareness:** Always subtract a 1-minute overlap to prevent gaps between windows

### Normalization
Every SOAR audit event is normalized to `automation.activity` schema before publishing:
```python
AutomationActivity(
    source_system="splunk",
    source_alert_id=event["container_id"],
    action=f"audit_{event['type']}",
    status=ActionStatus.succeeded,
    correlation_id=event.get("correlation_id", ""),
    executor={"type": "soar", "id": event.get("user", "unknown")},
)
```

### Frequency
- SOAR Audit Agent runs on a 5-minute timer
- Failure of one cycle does not block subsequent cycles
- Audit gap > 15 minutes triggers an alert to Agent Ops

## Circuit Breaker Protection

All SOAR API calls are wrapped in a `CircuitBreaker`:
- **Threshold:** 5 consecutive failures → OPEN
- **Reset Timeout:** 30 seconds → HALF_OPEN
- **Probe:** 1 successful call resets to CLOSED
- **User Impact:** Calls fail fast (`IntegrationError`) when circuit is OPEN

## Error Handling

| Status Code | Action | Retry |
|-------------|--------|-------|
| 200–299 | Success | Not needed |
| 401 | Refresh session key, retry once | 1 attempt |
| 429 | Exponential backoff (1s, 2s, 4s) | 3 attempts |
| 500, 502–504 | Exponential backoff or circuit open | 3 attempts + circuit breaker |
| 4xx (other) | Fail fast, log error | No retry |

## Guardrails

### Security
- HIGH-sensitivity containers must never send raw payload to hosted LLM providers
- ALL SOAR API calls must be logged to EventHub `audit` topic before returning
- `verify=True` with configurable CA bundle — never `verify=False` outside dev
- Session credentials never logged or exposed in error messages

### Operational
- Never re-trigger a playbook already in `running` state
- Container tags must always include `automation_source:magenta`
- Audit collection uses sliding windows with overlap, not absolute ranges
- Circuit breaker metrics must be visible in `/health/dependencies`

### Code
- All new SOAR API methods must go through `_request()` (circuit breaker wrapper)
- Response validation via Pydantic models before returning to caller
- Timestamp comparisons use `datetime.utcnow()` throughout

## Cross-Domain Interfaces

| Domain | Interaction |
|--------|-------------|
| **Backend** | Provides `SOARConnector` for integration code; orchestrator dispatches via `SOARDispatcher` |
| **Data** | Consumes SOAR audit events normalized to `automation.activity` schema |
| **Frontend** | Displays SOAR dispatch status, container state, playbook run history |
| **QA** | Tests SOAR connector with mock server; validates idempotency and circuit breaker behavior |
| **Ops** | Monitors circuit breaker metrics, SOAR API latency, and audit trail completeness |
