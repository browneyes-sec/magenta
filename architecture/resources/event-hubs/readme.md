# Event Hubs Architecture & Sizing

## Component Overview

Azure Event Hubs serves as the **Security Automation Bus** — the central message backbone connecting all agents in the Magenta fabric. Every agent publishes and subscribes to typed topics, enabling decoupled, asynchronous, and scalable communication.

From the DTP (§2.1):

```
raw-alerts ──► enriched-alerts ──► actions ──► audit
     │                │                │           │
 Source          Normalizer        Orchestrator   Registry
 Agents          + Enrichment      + Execution    Agent
```

## Topic Topology

| Topic | Schema | Retention | Partition Count | Produced By | Consumed By |
|---|---|---|---|---|---|
| `raw-alerts` | Source-native JSON (Sentinel incident, Splunk alert) | 7 days | 4-8 | Source Agents (Sentinel, Splunk) | Normalizer Agent |
| `enriched-alerts` | Canonical ASIM-aligned `automation.activity` | 1 day | 4-8 | Normalizer Agent, Enrichment Agent | Orchestrator Agent |
| `actions` | Action request envelope | 1 day | 2-4 | Orchestrator Agent | Execution Agent, Registry Agent |
| `audit` | Completed `automation.activity` | 7 days | 2-4 | Execution Agent, Registry Agent | Registry Agent (sink) |

## Partitioning Strategy

```yaml
eventhub:
  namespace: magenta-agent-bus
  topics:
    raw-alerts:
      partitions: 8
      retention_hours: 168  # 7 days
      capture_enabled: true
      capture_format: Parquet
      partition_key_source: correlation_id  # ensures alert ordering per incident
    enriched-alerts:
      partitions: 8
      retention_hours: 24
      partition_key_source: correlation_id
    actions:
      partitions: 4
      retention_hours: 24
      partition_key_source: target_type  # isolates host/network/identity actions
    audit:
      partitions: 4
      retention_hours: 168
      capture_enabled: true
      capture_format: Parquet
```

Partition count formula: `max(throughput_MBps / 1, concurrent_consumers × 2)`

| Alert Volume | Recommended Partitions (raw-alerts) |
|---|---|
| < 100 alerts/day | 2 |
| 100-1000 alerts/day | 4 |
| 1000-10000 alerts/day | 8 |
| > 10000 alerts/day | 16+ (Premium tier) |

## Consumer Groups

Each agent role gets a dedicated consumer group, allowing independent offset tracking:

| Consumer Group | Agents | Purpose |
|---|---|---|
| `$Default` | — | Reserved |
| `normalizer` | Normalizer Agent | Read raw-alerts |
| `enricher` | Enrichment Agent | Read enriched-alerts |
| `orchestrator` | Orchestrator Agent | Read enriched-alerts |
| `executor` | Execution Agent | Read actions |
| `registry` | Registry Agent | Read audit |
| `soar-audit` | SOAR Audit Agent | External SOAR audit |

## Event Hubs Capture

Zero-code archival to Data Lake Gen2:

```bash
# Enabled per topic via Azure Portal / ARM / Bicep
az eventhubs eventhub update \
    --namespace magenta-agent-bus \
    --name raw-alerts \
    --capture-enabled true \
    --capture-interval 300 \
    --capture-size-limit 314572800 \  # 300 MB
    --capture-destination-name magenta-lake \
    --capture-format Parquet \
    --capture-archive-name-format "{Namespace}/{EventHub}/{PartitionId}/{Year}/{Month}/{Day}/{Hour}/{Minute}/{Second}"
```

Capture output path:
```
magenta-lake/
├── raw-alerts/
│   └── Ehns_magenta-agent-bus/raw-alerts/0/2026/06/13/14/30/00.parquet
├── enriched-alerts/
└── audit/
```

## Throughput & Sizing

| Tier | Throughput Units | Ingress MBps | Egress MBps | Max Partitions |
|---|---|---|---|---|
| Standard | 1-20 (auto-inflate) | 1 per TU | 2 per TU | 32 |
| Premium | 1-100 processing units | 10 per PU | 20 per PU | 100 |
| Dedicated | 1 CU (200 TU equivalent) | 200 MBps | 400 MBps | 2000 |

For Magenta workloads:
- **Dev/Staging**: Standard tier, 1 TU, auto-inflate to 4
- **Production < 1000 alerts/day**: Standard tier, 2 TU, auto-inflate to 8
- **Production > 1000 alerts/day**: Premium tier, 2 PU

## Kafka Endpoint

```python
# Kafka-compatible producer
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers="magenta-agent-bus.servicebus.windows.net:9093",
    security_protocol="SASL_SSL",
    sasl_mechanism="PLAIN",
    sasl_plain_username="$ConnectionString",
    sasl_plain_password=conn_str,
    value_serializer=lambda v: json.dumps(v).encode(),
)

producer.send("raw-alerts", value=alert, key=correlation_id.encode())
```

## Dead-Letter Queue

Events that fail schema validation or processing are routed to a DLQ topic:

```yaml
eventhub:
  dlq_topic: dead-letter
  dlq_retention_hours: 48
  dlq_capture: true
```

```python
async def publish_with_dlq(topic: str, event: dict, error: Optional[str] = None):
    try:
        await validate_schema(event)
        await producer.send(topic, event)
    except SchemaError:
        event["_dlq"] = {"reason": str(error), "original_topic": topic, "timestamp": utcnow()}
        await producer.send("dead-letter", event)
```

## Monitoring

| Metric | Alert |
|---|---|
| Consumer lag > 1000 (any group) | Critical |
| Throttled requests > 1% | Warning — increase TUs/PUs |
| Capture backlog > 5 min | Warning |
| Dead-letter rate > 1% | Investigate |
| Partition skew > 20% | Rebalance partition key |
