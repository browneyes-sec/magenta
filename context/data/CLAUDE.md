# Data Agent Context

## Domain
Schema registry, Delta/Parquet pipelines, Elasticsearch mappings, Sentinel custom tables, data governance.

## Technology Stack
- **Storage:** Azure Data Lake Gen2 (Parquet/Delta), Elasticsearch 8.x, Azure Table Storage
- **Processing:** Delta Lake, Event Hubs Capture (Avro → Parquet)
- **Monitoring:** Azure Monitor, Application Insights, Elasticsearch ILM
- **Schema:** Pydantic v2 `AutomationActivity` → JSON → Parquet/Delta

## Schema Registry Ownership

The `automation.activity` schema is the canonical event contract for the entire platform. The Data Agent owns its evolution.

### Schema Evolution Rules
- `schema_version` field is mandatory and must be incremented on any breaking change
- Breaking changes: field removal, type change, required → optional inversion
- Non-breaking: field addition (must be optional), description changes, default value changes
- Schema version bumps require **Architecture Change Board sign-off**
- All new fields must be optional for the first version to ensure backward compatibility

### Current Schema
```python
class AutomationActivity(BaseModel):
    schema_version: str = "1.0"
    event_type: str = "automation.activity"
    event_id: str = "<uuid>"
    correlation_id: str = "<uuid>"
    idempotency_key: str = "<sha256>"
    source_system: Literal["sentinel", "splunk"]
    action: str
    target: dict
    status: ActionStatus
    executor: dict
    # ... see magenta/core/models.py for full definition
```

## Delta Lake Write Patterns

### Partition Strategy
```
date=YYYY-MM-DD/
  source_system=sentinel/
    *.parquet
  source_system=splunk/
    *.parquet
```

### Write Configuration
- **Mode:** `append` only — never overwrite partitions
- **Dedup column:** `idempotency_key`
- **Compression:** Snappy for Parquet, Zstd for Delta checkpoints
- **Schema merge:** `mergeSchema=true` for non-breaking additions
- **Vacuum retention:** 7 days minimum

## Elasticsearch Index Convention

### Index Pattern
```
automation-activity-YYYY.MM
```

### ILM Policy
| Phase | Duration | Action |
|-------|----------|--------|
| Hot | 30 days | Writeable, SSD-backed |
| Warm | 60 days | Read-only, HDD-backed |
| Cold | 90 days | Frozen, searchable |
| Delete | 365 days | Remove |

### Mapping Rules
- `dynamic: false` at root level to prevent schema drift
- Explicit mapping for filterable fields: `correlation_id`, `source_system`, `action`, `status`, `risk_score`
- `idempotency_key` mapped as keyword with `index: true` for dedup queries

## Sentinel Log Ingestion

### Data Collection Rules (DCR)
- DCR endpoints target `SecurityAutomationActivity_CL` custom table
- Schema must match DCR-defined transformation exactly
- Table columns are dynamically created on first ingestion, but type changes require DCR update

### Batch Configuration
- Max batch size: 100 records per POST
- Max payload size: 1 MB per POST
- Retry on `429` and `5xx` with exponential backoff (1s, 2s, 4s)

## Guardrails
- NEVER change `schema_version` without Architecture Change Board sign-off
- ALL Parquet writes must use `append` mode with `idempotency_key` dedup
- ES index template changes must be backward-compatible with existing data
- Never delete historical partitions — use ILM for data lifecycle
- All Delta table schema changes must be validated against existing data
- Never write directly to production Elasticsearch indices without ILM policy

## Cross-Domain Interfaces

| Domain | Interaction |
|--------|-------------|
| **Backend** | Consumes `automation.activity` writes from Registry Agent |
| **SOAR** | Receives normalized audit events for correlation |
| **Frontend** | Reads from Elasticsearch for dashboards and activity ledger |
| **QA** | Validates schema conformance via dead-letter rate < 1% |
| **Ops** | Manages Data Lake lifecycle, backup, and disaster recovery |
