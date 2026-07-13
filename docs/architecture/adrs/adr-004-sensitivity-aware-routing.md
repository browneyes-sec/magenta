# ADR-004: Sensitivity-Aware LLM Routing

## Status
Accepted

## Context
The `llm-policy.md` mandates that `HIGH`-sensitivity missions must only route to local Ollama models — no external provider egress is permitted. The original `ModelRouter` routed purely by performance tier (`speed`, `reasoning`, `cost_save`) with no awareness of the sensitivity level of the calling agent's mission context. This created a compliance gap: a HIGH-sensitivity alert containing PII or classified data could be sent to hosted LLM providers (Gemini, Groq, OpenRouter).

## Decision
Add `sensitivity_level` and `priority` fields to `ModelRequest`. The `ModelRouter.route()` method enforces:

- **HIGH sensitivity** → exclusively local Ollama clients; hosted providers are never attempted
- **MEDIUM sensitivity** → local preferred, hosted allowed with policy override
- **LOW sensitivity** → normal tier-based routing (existing behavior)

The default is `sensitivity_level="LOW"` to preserve backward compatibility.

## Rationale
- **Policy before model**: routing decisions are governed by security policy, not performance optimization
- **Default-safe**: HIGH-sensitivity data never leaves controlled environments
- **Backward-compatible**: existing agents default to LOW, preserving current behavior
- **Field on ModelRequest**: sensitivity context is carried with the request, not inferred from caller identity

## Consequences
- Positive: Compliance with `llm-policy.md` sensitivity routing
- Positive: All existing code continues to work unchanged
- Negative: HIGH-sensitivity missions may fail if no Ollama models are available (fail-closed)
- Trade-off: Agents must explicitly declare sensitivity context; failure to do so defaults to LOW

## Compliance
- Any workflow bypassing `model_router.route()` fails deployment (CI/CD gate)
- HIGH-sensitivity requests are verified to only reach Ollama endpoints
- Audit log records sensitivity_level for every LLM call
