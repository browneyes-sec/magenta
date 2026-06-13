# Database Architecture & Sizing

## Component Overview

Magenta uses SQL persistence for:

- **Mission registry** — canonical record of all missions, agents, and tasks
- **Playbook store** — versioned playbook YAML/JSON/TOML
- **Activity log** — `automation.activity` events for audit and compliance
- **Agent configuration** — agent definitions, model assignments, tool bindings

Current implementation uses SQLAlchemy async ORM with SQLite (dev) → PostgreSQL (prod).

## Schema

### `automation_activity` — Canonical Activity Table

```sql
CREATE TABLE automation_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_version VARCHAR(10) NOT NULL DEFAULT '1.0',
    event_type VARCHAR(50) NOT NULL DEFAULT 'automation.activity',
    event_id UUID NOT NULL UNIQUE,
    correlation_id UUID NOT NULL,
    idempotency_key VARCHAR(64) NOT NULL,
    source_system VARCHAR(20) NOT NULL,
    source_workspace_id VARCHAR(100),
    source_alert_id VARCHAR(255),
    source_incident_id VARCHAR(255),
    playbook_id VARCHAR(100),
    playbook_run_id VARCHAR(100),
    action VARCHAR(50) NOT NULL,
    target JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    approval JSONB,
    risk_score INTEGER DEFAULT 0,
    blast_radius VARCHAR(20),
    mitre_tactics TEXT[],
    executor JSONB,
    evidence JSONB,
    tags TEXT[],
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_activity_correlation ON automation_activity(correlation_id);
CREATE INDEX idx_activity_alert ON automation_activity(source_alert_id);
CREATE INDEX idx_activity_status ON automation_activity(status);
CREATE INDEX idx_activity_created ON automation_activity(created_at DESC);
CREATE UNIQUE INDEX idx_activity_idempotency ON automation_activity(idempotency_key);
```

### `missions` — Mission State Table

```sql
CREATE TABLE missions (
    mission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(20) NOT NULL DEFAULT 'created',
    alert_id VARCHAR(255),
    source_system VARCHAR(20),
    playbook_id VARCHAR(100),
    playbook_version VARCHAR(20),
    severity INTEGER DEFAULT 3,
    risk_score INTEGER DEFAULT 0,
    description TEXT,
    team JSONB,
    tasks JSONB,
    artifact_bundle JSONB,
    correlation_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

### `agent_logs` — Per-Agent Turn Log

```sql
CREATE TABLE agent_logs (
    id BIGSERIAL PRIMARY KEY,
    agent_id VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL,
    mission_id UUID,
    model VARCHAR(100),
    prompt TEXT,
    response TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    latency_ms INTEGER,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Connection Pooling

```yaml
sql:
  url: postgresql+asyncpg://magenta:password@pg-cluster:5432/magenta
  pool_size: 10           # per worker
  max_overflow: 20         # burst connections
  pool_timeout: 30         # seconds
  pool_recycle: 1800       # seconds
  echo: false
```

Formula: `total_connections = workers × (pool_size + max_overflow)`

| Workers | pool_size | max_overflow | Total Connections |
|---|---|---|---|
| 4 | 10 | 20 | 120 |
| 8 | 10 | 20 | 240 |
| 4 | 20 | 40 | 240 |

## Partitioning Strategy

For the `automation_activity` table at scale (>10M rows/month):

```sql
-- Range partition by month
CREATE TABLE automation_activity (
    LIKE automation_activity_template INCLUDING ALL
) PARTITION BY RANGE (created_at);

CREATE TABLE automation_activity_2026_01
    PARTITION OF automation_activity
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE automation_activity_2026_02
    PARTITION OF automation_activity
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
```

## Migration Strategy

```bash
# Alembic
alembic init migrations
alembic revision --autogenerate -m "add activity table"
alembic upgrade head
```

Environment-based:
- **Dev**: `sqlite+aiosqlite:///data/magenta.db` — auto-migrate on startup
- **Staging**: PostgreSQL — Alembic in CI/CD pipeline
- **Prod**: PostgreSQL with blue/green migration — zero-downtime via `CREATE TABLE` + rename

## Monitoring

| Metric | Alert |
|---|---|
| Connection pool utilization > 80% | Warning |
| Query latency p99 > 500 ms | Warning |
| Replication lag > 5 s | Warning |
| Deadlocks / hour > 0 | Investigate |
| Table bloat > 30% | Schedule VACUUM |
