# ADR-005: Circuit Breaker Pattern for Integration Layer

## Status
Accepted

## Context
All integration connectors (Sentinel, Splunk, SOAR) lacked any resilience pattern. A SIEM API timeout could cause agent threads to pile up, exhausting connection pools and cascading failures across the platform. The assessment found no circuit breakers, retry policies, or bulkhead patterns in any connector.

The `llm-policy.md` specifies exponential backoff on 429/5xx, but this was not implemented.

## Decision
Create a `CircuitBreaker` utility class (`magenta/core/circuit_breaker.py`) with a three-state state machine:

- **CLOSED** — calls pass through normally; failure counter increments on each failure
- **OPEN** — after `failure_threshold` consecutive failures; calls fail fast with `IntegrationError`
- **HALF_OPEN** — after `reset_timeout` seconds; one probe call determines whether to reset to CLOSED or return to OPEN

All integration connectors wrap external calls through a `CircuitBreaker` instance. Exponential backoff (1s, 2s, 4s) is implemented at the connector level before the circuit breaker.

## Rationale
- **Fail fast**: when SOAR is down, don't waste agent time waiting for timeouts
- **Self-healing**: after reset timeout, the circuit automatically probes for recovery
- **Prevents cascade**: a single failing integration doesn't block unrelated agent work
- **Observable**: metrics expose circuit state per integration

## Consequences
- Positive: Integration failures are isolated to their circuit breaker
- Positive: Circuits self-heal without operator intervention
- Negative: First call after HALF_OPEN transition may fail (acceptable cost for resilience)
- Risk: Aggressive failure thresholds may trip during transient network issues (mitigated by min threshold of 3)

## Compliance
- Every external API call in integration connectors must use a `CircuitBreaker`
- Circuit metrics must be exposed via `/health/dependencies`
