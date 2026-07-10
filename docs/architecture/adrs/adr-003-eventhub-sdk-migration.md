# ADR-003: EventHub SDK Migration

## Status
Accepted

## Context
The original `EventHubClient` in `magenta/integration/eventhub.py` was entirely stubbed: `send()` returned synthetic dicts, `_consume_loop()` ran `asyncio.sleep(1)` with no Azure SDK calls. This meant the entire agent-to-agent messaging fabric was disconnected from Azure Event Hubs — no events were actually published or consumed.

The production requirement (DTP §2.1, §7) demands real Event Hubs integration with:
- Checkpointed consumer offsets (Blob CheckpointStore)
- Per-agent consumer group isolation
- Dead-letter handling for schema failures
- Lag metrics and auto-inflate signaling

## Decision
Replace the stub with a full `azure-eventhub` SDK implementation. The new `EventHubClient` uses:
- `EventHubProducerClient` for `send()` and `send_batch()`
- `EventHubConsumerClient` with `BlobCheckpointStore` for consumer offset management
- Partition-aware event processing with checkpoint-after-success semantics
- Dead-letter topic for schema validation failures

## Rationale
- **Checkpoint store** ensures consumers resume from last processed event (not stream head) on restart
- **Per-agent consumer groups** prevent offset interference between normalizer, enrichment, orchestrator, and registry agents
- **Dead-letter handling** prevents one bad event from blocking the entire consumer

Rejected alternatives:
- Kafka-python library (Event Hubs Kafka endpoint) — adds protocol translation overhead
- In-memory checkpointing — loses position on restart, causing duplicate or missed events

## Consequences
- Positive: Consumer restart is safe — no duplicate or missed events
- Positive: Each agent role has isolated offset tracking
- Negative: Adds `azure-eventhub` and `azure-eventhub-checkpointstoreblob-aio` as runtime dependencies
- Risk: Blob storage for checkpoints becomes a dependency for consumer functionality

## Compliance
- All agent consumers must use a dedicated consumer group
- All consumed events must be checkpointed after successful processing only
- Schema validation failures must go to the dead-letter topic
