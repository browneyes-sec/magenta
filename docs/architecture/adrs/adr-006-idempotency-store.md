# ADR-006: Idempotency via Azure Table Storage

## Status
Accepted

## Context
The `AutomationActivity` model generates idempotency keys via SHA-256 of `(source_alert_id, action, target_id)`, but there was no check-before-act store. During agent restarts, Event Hubs redelivery, or orchestrator retries, the same action could be executed twice — potentially causing duplicate account disabling, host isolation, or ticket creation.

The DTP risk register (§9) identifies duplicate action execution as a Medium-likelihood, High-impact risk.

## Decision
Implement an `IdempotencyStore` backed by Azure Table Storage with a 24-hour TTL. The store exposes:
- `check_and_register(alert_id, action, target_id)` → returns True (new) or raises `DuplicateActionError`
- `exists(alert_id, action, target_id)` → boolean check without registering

An in-memory fallback (`_InMemoryTable`) is used when Azure Table Storage is unavailable (development, testing).

## Rationale
- **Check-before-act**: the Execution Agent must check the store BEFORE firing any action
- **24-hour TTL**: covers the maximum replay window for Event Hubs retention + agent restart
- **Azure Table Storage**: serverless, cost-effective, no infrastructure to manage
- **In-memory fallback**: development and testing without Azure dependencies
- **Fail-open**: if the store is unavailable, the action is allowed (safety over consistency for availability)

## Consequences
- Positive: Zero duplicate actions across restart scenarios
- Positive: Event Hubs redelivery is safe — events processed multiple times skip duplicate actions
- Risk: Fail-open during store unavailability could still produce duplicates (mitigated by TTL-based retry)
- Dependency: `azure-data-tables` package required for production

## Compliance
- Every Execution Agent action must call `check_and_register` before executing
- `DuplicateActionError` must be logged and the action skipped, not retried
