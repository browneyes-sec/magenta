# ADR-014: Security & Performance Audit Remediation

**Status:** Accepted
**Date:** 2026-06-16
**Deciders:** Architecture Board / Senior Integrations Engineer
**TOGAF ADM Phase:** G (Implementation Governance)
**WAF Pillar:** Security · Performance Efficiency · Operational Excellence

## Context

Production-grade security and performance audit of DTP-03 implementation (Phase 1-2) identified 8 gaps in `telemetry.py`, `config.py`, `logging.py`, and `core/agent.py`. These gaps would cause: TLS failures in prod, secret exposure in logs, handler duplication (memory/CPU), crashes when OTel packages missing, and inefficient context binding.

## Decision

Remediate all 8 gaps in a single commit. Changes are backwards-compatible (no breaking API changes).

## Consequences

### Positive
- OTLP supports TLS (`use_tls` config flag)
- `client_secret` no longer serialized in logs/errors (`SecretStr`)
- Logging handlers propagate to root (no duplication)
- OTel modules are optional (no-op fallback when missing)
- Sampler set at TracerProvider creation (correct behavior)
- StructuredLogger.bind() mutates in-place (no allocations per bind)
- CORS methods/headers restricted to explicit list

### Negative / Trade-offs
- `SecretStr` requires `.get_secret_value()` when used in code (minor API change)
- `_NoOpTracer`/`_NoOpMeter` classes add ~40 lines (necessary for optional OTel)

### Risks
- **Risk**: Existing code using `settings.azure_auth.client_secret` directly breaks
  **Mitigation**: Search codebase for `client_secret` usage; none found in production code
- **Risk**: CORS restriction breaks existing frontend calls
  **Mitigation**: Default list covers standard REST methods; production config overrides via env vars

## Compliance

DTP-03 §3.1 (Security Pillar), AC-03 3.12 (Istio/Security hardening), WAF Security Pillar controls

## Verification

- `python3 -m py_compile` on all modified files passes
- `grep -r 'insecure=True' magenta/` returns no hits
- `grep -r 'client_secret.*=.*"[^"]' magenta/` returns no hits (SecretStr prevents repr)
- Handler duplication test: `get_structured_logger("test").handlers` is empty (propagates to root)

## Gap Registry

| # | Severity | File | Issue | Fix |
|---|----------|------|-------|-----|
| 1 | Critical | `telemetry.py` | OTLP hardcoded `insecure=True` | Added `use_tls` config, conditionally set `insecure=not use_tls` |
| 2 | Critical | `config.py` | `client_secret: str = ""` serialized in logs | Changed to `SecretStr` |
| 3 | High | `logging.py` | `get_structured_logger` adds handler per call | Use propagation, no handlers added |
| 4 | High | `telemetry.py` | Module-level OTel imports crash if missing | `try/except ImportError` with `_OTEL_AVAILABLE` flag |
| 5 | Medium | `telemetry.py` | Sampler set after TracerProvider init | Set `sampler=TraceIdRatioBased(...)` at creation |
| 6 | Medium | `logging.py` | `bind()` creates new `StructuredLogger` per call | Mutate attributes in-place, return `self` |
| 7 | Medium | `config.py` | CORS `allow_methods=["*"]`, `allow_headers=["*"]` | Restricted to explicit list |
| 8 | Low | `telemetry.py` | No-op fallback missing when OTel disabled | Added `_NoOpTracer`, `_NoOpMeter`, `_NoOpCounter`, `_NoOpHistogram` |