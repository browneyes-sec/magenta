# Normalization Architecture

## Component Overview

The Normalizer Agent transforms vendor-specific alert payloads (Sentinel incidents, Splunk alerts) into a canonical ASIM-aligned schema. This ensures downstream agents (Orchestrator, Registry) process a uniform event format regardless of source.

DTP reference: §2.2 (Normalizer Agent), §2.3 (Canonical Schema)

## Pipeline

```
raw-alerts (vendor-specific)
    │
    ▼
┌─────────────────────────────────────┐
│         Normalizer Agent            │
│                                     │
│  1. Identify source system          │
│  2. Load vendor mapping             │
│  3. Map fields → canonical schema   │
│  4. Validate against schema         │
│  5. Generate correlation_id         │
│  6. Publish to enriched-alerts      │
│     OR dead-letter on failure       │
└─────────────────────────────────────┘
    │
    ▼
enriched-alerts (canonical)
```

## Canonical Schema

Every event on `enriched-alerts` follows the `automation.activity` schema defined in the DTP (§2.3):

```json
{
  "schema_version": "1.0",
  "event_type": "automation.activity",
  "event_id": "<uuid>",
  "correlation_id": "<uuid>",
  "idempotency_key": "<sha256(source_alert_id + action + target_id)>",
  "source_system": "sentinel | splunk",
  "source_workspace_id": "<workspace_id>",
  "source_alert_id": "<alert_id>",
  "source_incident_id": "<incident_id>",
  "action": "disable_account | isolate_host | create_ticket | block_ip | ...",
  "target": {
    "type": "user | host | ip | process",
    "id": "<entity_identifier>",
    "asset_criticality": "critical | high | medium | low"
  },
  "status": "received",
  "risk_score": 0,
  "blast_radius": "single-user | subnet | domain",
  "mitre_tactics": ["TA0001", "TA0003"],
  "started_at": "<ISO8601>",
  "executor": {
    "type": "source_agent",
    "id": "sentinel-source-01"
  },
  "evidence": {
    "raw_alert_ref": null
  },
  "tags": ["severity:high", "source:sentinel"]
}
```

## Vendor Mappings

### Sentinel → Canonical

| Sentinel Field | Canonical Field | Transform |
|---|---|---|
| `Incident.properties.incidentNumber` | `source_alert_id` | Direct |
| `Incident.properties.title` | Tags: `title` | Slugified |
| `Incident.properties.severity` | `tags: severity` | Map: Critical→5, High→4, Medium→3, Low→2 |
| `Incident.properties.createdTimeUtc` | `started_at` | Parse ISO 8601 |
| `Incident.properties.tactics` | `mitre_tactics` | Direct |
| `Incident.properties.systemAlertId` | `source_incident_id` | Direct |
| `workspaceId` | `source_workspace_id` | From connection context |
| `Incident.properties.additionalData.alertProductNames` | `tags: product` | First product name |

### Splunk → Canonical

| Splunk Field | Canonical Field | Transform |
|---|---|---|
| `result.id` or `sid` | `source_alert_id` | Coalesce with fallback |
| `search_name` | Tags: `search_name` | Direct |
| `result.severity` | `tags: severity` | Map: critical→5, high→4, medium→3, low→2 |
| `result.src_ip` | `target.id` | If type=ip |
| `result.user` | `target.id` | If type=user |
| `result.dest` | `target.id` | If type=host |
| `_time` | `started_at` | Parse epoch/ISO |

## Normalizer Implementation

```python
# Conceptual: Normalizer Agent
class NormalizerAgent:
    SOURCE_MAPPINGS = {
        "sentinel": SentinelMapping(),
        "splunk": SplunkMapping(),
    }

    async def normalize(self, raw_event: dict) -> dict:
        source = self._detect_source(raw_event)
        mapper = self.SOURCE_MAPPINGS.get(source)
        if not mapper:
            raise UnknownSourceError(source)

        canonical = mapper.map(raw_event)
        canonical["correlation_id"] = str(uuid4())
        canonical["event_id"] = str(uuid4())
        canonical["schema_version"] = "1.0"
        canonical["event_type"] = "automation.activity"

        self._validate(canonical)
        return canonical

    def _validate(self, event: dict):
        required = ["correlation_id", "source_system", "source_alert_id", "started_at"]
        missing = [f for f in required if not event.get(f)]
        if missing:
            raise SchemaValidationError(f"Missing fields: {missing}")
```

## Schema Versioning

```yaml
schema:
  current: "1.0"
  versions:
    "1.0":
      required: [correlation_id, source_system, source_alert_id, started_at, event_id]
      optional: [mitre_tactics, target, tags, evidence]
      breaking_changes_from: null
```

Schema evolution follows a backward-compatible policy: new fields are added, existing fields are never removed or renamed.

## Dead-Letter Criteria

Events are routed to `dead-letter` when:

| Condition | Example |
|---|---|
| Unknown source system | `source_system: "unknown-vendor"` |
| Missing required field | No `source_alert_id` |
| Field type mismatch | `started_at` not parseable as ISO 8601 |
| Payload too large | > 1 MB raw payload |

## Monitoring

| Metric | Alert |
|---|---|
| Normalization failure rate > 2% | Warning |
| Schema validation errors > 1% | Warning |
| Unknown source system count > 0 | Warning — new connector needed |
| Dead-letter queue depth > 100 | Investigate |
| Normalization latency p99 > 500 ms | Warning |
