# ADR-001: Registry Triple-Write Pattern

## Status
Accepted

## Context
The Magenta platform's core value proposition is providing an immutable, auditable automation telemetry registry. Every agent action must be recorded as an `automation.activity` event. The original implementation in `LLMAgent.log_activity()` was a stub returning `None` — no events were actually persisted.

Three registry sinks are required by the architecture (DTP §2.6):
1. **Elasticsearch** — hot index for operational queries (30-day retention)
2. **Sentinel custom table** — SIEM-native queries via `SecurityAutomationActivity_CL`
3. **Azure Data Lake Delta** — long-term compliance archive (1-7 year retention)

## Decision
Implement an async triple-write to all three sinks concurrently using `asyncio.gather(return_exceptions=True)`. Registry failures must never propagate to the calling agent. Failed writes go to an in-memory dead-letter queue for retry.

The `RegistryWriter` class in `magenta/core/registry.py` is the single entry point. Each sink write is an independent coroutine. The `LLMAgent.log_activity()` calls `registry_writer.write_activity()` which fans out to all three sinks.

## Rationale
- **Fire-and-forget** prevents registry latency from blocking mission execution
- **Concurrent writes** minimize total write latency (all three complete in ~max(latency) not sum(latency))
- **Dead-letter queue** provides observability without blocking the agent pipeline
- **Single entry point** allows future schema validation, signing, and batching at one location

Rejected alternatives:
- **Synchronous serial writes** — would block agent execution and multiply latency
- **Background queue worker** — adds infrastructure complexity; agent would need ACK tracking
- **Write to EventHub only** — doesn't meet the DTP requirement for three independent sinks

## Consequences
- Positive: Registry writes are non-blocking by design
- Positive: Each sink can evolve independently (ES schema changes don't affect Delta)
- Negative: Dead-letter queue is in-memory; process restart loses queued entries (acceptable for dev)
- Risk: Failed writes are silent unless monitored via dead-letter queue metrics

## Compliance
- Every `LLMAgent.process()` call must terminate with `log_activity()`
- Registry failures must never propagate (enforced via `return_exceptions=True`)
- `RegistryWriter` is the only path to write automation events
