# Data Mesh Architecture — Magenta ASOAR

**Version:** 1.0 (Phase 1)
**Scope:** Core vectorization pipeline + external database integration (SQL + NoSQL)
**Deferred:** Analytics resources, blob/binary artifact ingestion

---

## 1. What Is the Magenta Data Mesh?

The data mesh is a **vectorized semantic layer** that unifies Magenta's source domains (SIEM, SOAR, external databases, NoSQL stores, identity, threat intel) into a single queryable fabric. It applies the four data mesh principles to the ASOAR context:

| Principle | ASOAR Application |
|---|---|
| **Domain ownership** | Each team owns its source systems and publishes data products |
| **Data as a product** | Every source domain exposes curated, documented, versioned data products |
| **Self-serve infrastructure** | Mesh gateway provides unified query without building per-source connectors |
| **Federated governance** | Cross-domain schema registry, data quality SLAs, access control per agent role |

The mesh exists to serve **agent memory and context** — every agent query, episode recall, and RAG pipeline goes through the mesh rather than accessing sources directly.

---

## 2. Logical Architecture (Phase 1)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CONSUMPTION LAYER                                    │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐   │
│  │  Web API          │  │  Agent Memory     │  │  Swarm Context       │   │
│  │  (FastAPI         │  │  - Episodic       │  │  - Mission state     │   │
│  │   /api/v1/mesh/*) │  │  - Semantic       │  │  - RAG retrieval     │   │
│  │                   │  │  - Procedural     │  │  - Tool patterns     │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘   │
│                          │                       │                       │
│                          ▼                       ▼                       │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                VECTORIZED DATA MESH PLANE                            │  │
│  │                                                                      │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │           MESH GATEWAY (FastAPI extension)                     │  │  │
│  │  │  /mesh/query   — hybrid search (dense + sparse + metadata)    │  │  │
│  │  │  /mesh/ingest  — push documents for vectorization             │  │  │
│  │  │  /mesh/products — data product catalog                        │  │  │
│  │  │  /mesh/health  — component health                             │  │  │
│  │  │  Query federation — cross-product joins via correlation_id    │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  │                                                                      │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │  │
│  │  │  VECTOR      │  │  SPARSE     │  │  METADATA   │  │  SQL       │ │  │
│  │  │  INDEX       │  │  INDEX      │  │  FILTER     │  │  FEDERATOR │ │  │
│  │  │  (Qdrant)    │  │  (BM25)     │  │  (Redis)    │  │  (PG/MySQL)│ │  │
│  │  └──────┬───────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │  │
│  │         │                 │                │               │         │  │
│  │         └─────────────────┴────────────────┴───────────────┘         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
│  ┌─────────────────────────────────▼────────────────────────────────────┐  │
│  │                      VECTORIZATION PIPELINE                           │  │
│  │                                                                       │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────┐  │  │
│  │  │  Source  │  │  Chunker │  │Embedder  │  │  Indexer │  │Sync   │  │  │
│  │  │Adapter   │→│(semantic │→│(OLLAMA   │→│(Qdrant  │→│Mgr   │  │  │
│  │  │          │  │ /token)  │  │ nomic /  │  │ upsert)  │  │       │  │  │
│  │  │          │  │          │  │ bge-m3)  │  │          │  │       │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └───────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
├────────────────────────────────────┼──────────────────────────────────────┤
│  ┌─────────────────────────────────▼────────────────────────────────────┐  │
│  │                      SOURCE DOMAINS                                   │  │
│  │                                                                       │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │  │
│  │  │  SIEM    │ │  SOAR    │ │External  │ │  NoSQL   │ │Identity   │  │  │
│  │  │ Sentinel │ │ Splunk   │ │ SQL      │ │ CosmosDB │ │ Entra ID  │  │  │
│  │  │ Splunk   │ │ SOAR     │ │ PG/MySQL  │ │ MongoDB  │ │           │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────────┘  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────────────────────────┐  │  │
│  │  │ Threat   │ │ Event    │ │  Event Hubs Topics                    │  │  │
│  │  │ Intel    │ │ Hubs     │ │  raw-alerts, enriched-alerts,        │  │  │
│  │  │ VT/Shodan│ │ (CDC)    │ │  actions, audit, cdc-{source}        │  │  │
│  │  └──────────┘ └──────────┘ └──────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Product Catalog

Every data product is a versioned, documented, queryable asset published by a source domain.

### 3.1 SIEM Data Products

| Product | Source | Vectorized | Schema |
|---|---|---|---|
| `siem.alerts` | Sentinel Incidents + SecurityAlert | Yes | incident_id, title, severity, mitre_tactics, entities[] |
| `siem.splunk.alerts` | Splunk fired_alerts | Yes | sid, search_name, severity, source, raw |

### 3.2 SOAR Data Products

| Product | Source | Vectorized | Schema |
|---|---|---|---|
| `soar.actions` | Splunk SOAR audit | Yes | action, playbook_id, status, target, risk_score |
| `soar.playbooks` | Playbook definitions | Yes | playbook_id, version, steps[], tags |

### 3.3 External SQL Data Products

| Product | Source | Sync Mode | Vectorized |
|---|---|---|---|
| `external.sql.servicenow` | ServiceNow CMDB, incidents | CDC (Debezium → Event Hubs) | Yes |
| `external.sql.asset_db` | Internal asset inventory | CDC or scheduled batch | Yes |
| `external.sql.custom` | Any user-defined SQL source | Debezium / poll + watermark | Optional |

### 3.4 NoSQL Data Products

| Product | Source | Sync Mode | Vectorized |
|---|---|---|---|
| `external.nosql.cosmos` | Cosmos DB containers | Change Feed → Event Hubs | Yes |
| `external.nosql.mongodb` | MongoDB collections | Change Streams → Event Hubs | Yes |

### 3.5 Identity & Threat Intel

| Product | Source | Vectorized | Schema |
|---|---|---|---|
| `identity.directory` | Entra ID users, groups, devices | Yes | object_id, display_name, department, roles[] |
| `threat.intel.iocs` | VirusTotal, Shodan, OTX | Yes | indicator, type, confidence, first_seen |

### 3.6 Agent Memory Data Products

| Product | Type | Vector Index | Retention |
|---|---|---|---|
| `agent.memory.episodic` | Mission transcripts, agent decisions | `mem-episodic` | 90 days |
| `agent.memory.semantic` | Knowledge base, playbooks, runbooks | `mem-semantic` | Indefinite |
| `agent.memory.procedural` | Tool usage patterns, delegation history | `mem-procedural` | 30 days |

### 3.7 Endpoint & Cloud Log Data Products (ADR-011)

| Product | Source | Vectorized | Qdrant Collection | Primary Consumer |
|---|---|---|---|---|
| `endpoint.windows.events` | WEF / AMA / WAC | Yes | `endpoint_windows` | Investigate agent |
| `endpoint.linux.syslog` | rsyslog / Fluent Bit | Yes | `endpoint_linux` | Investigate agent |
| `customer.logs.custom` | SFTP / HTTPS drops | Yes | `customer_custom` | Mission-specific RAG |
| `cloud.azure.activity` | Azure Monitor / DCR | Yes | `cloud_azure` | Enrichment, compliance |
| `cloud.azure.identity` | Entra ID Graph API | Yes | `cloud_azure_identity` | Identity audit |
| `cloud.aws.activity` | CloudTrail → Event Hubs | Yes | `cloud_aws` | Enrichment |
| `cloud.gcp.activity` | Cloud Logging → Event Hubs | Yes | `cloud_gcp` | Enrichment |

---

## 4. Vectorization Pipeline

### 4.1 Chunking Strategies

| Content Type | Strategy | Chunk Size | Overlap |
|---|---|---|---|
| Alert/incident text | Semantic split (sentence boundary) | 512 tokens | 64 tokens |
| Playbook steps | Document-level (keep structure) | N/A | N/A |
| SQL table rows | Row → document | N/A | N/A |
| NoSQL documents | Document → embedding | N/A | N/A |
| Identity directory | Entity → embedding | N/A | N/A |
| Threat intel reports | Semantic split (paragraph) | 1024 tokens | 128 tokens |
| Agent decision logs | Turn-level | 2048 tokens | 256 tokens |
| Windows Event XML | Semantic split on message body | 512 tokens | 64 tokens |
| Linux syslog (single-line) | Line-level | 256 tokens | 0 |
| Linux syslog (multi-line stack trace) | Stack trace grouping | 1024 tokens | 128 tokens |
| Cloud JSON (Azure/AWS/GCP activity) | Document-level (one activity = one embedding) | N/A | N/A |
| Customer custom (CSV/JSON/CEF) | Configurable per-source (TOML defined) | 512 tokens | 64 tokens |

### 4.2 Embedding Configuration

```yaml
embeddings:
  provider: ollama
  model: nomic-embed-text:v1.5
  dimension: 768
  batch_size: 32
  cache:
    ttl: 86400
    backend: redis
```

| Model | Dims | Quality | Speed | Use Case |
|---|---|---|---|---|
| `nomic-embed-text:v1.5` | 768 | Good | Fast | Default — all products |
| `bge-m3` | 1024 | Excellent | Moderate | Threat intel, complex playbooks |
| `all-MiniLM-L6-v2` | 384 | Adequate | Very Fast | High-volume alert pre-filtering |

### 4.3 Index Strategy (Qdrant)

Each data product maps to a Qdrant collection with a consistent payload schema:

```yaml
collections:
  siem_alerts:
    vectors:
      size: 768
      distance: Cosine
    payload_schema:
      product: siem.alerts
      source: sentinel | splunk
      incident_id: string
      severity: [low, medium, high, critical]
      timestamp: datetime
      correlation_id: string (nullable)
      mitre_tactics: string[]
      entities: string[]
    hnsw_config:
      m: 16
      ef_construct: 200
    optimizers:
      default_segment_number: 2
      memmap_threshold_kb: 20000
```

Hybrid search uses:
- **Dense vector** (embedding) — semantic similarity
- **Sparse vector** (BM25) — keyword relevance
- **Payload filters** — product, source, severity, time range, agent role

### 4.4 Sync Modes

| Mode | Mechanism | Latency | Use Case |
|---|---|---|---|
| **Real-time (CDC)** | Debezium / Change Feed → Event Hubs → vectorizer | < 30s | External DBs, NoSQL |
| **Scheduled batch** | Timer-triggered poll + watermark | 5–60 min | SIEM queries, threat intel APIs |
| **On-demand** | `POST /mesh/ingest` via API | Immediate | Agent memory writes, playbook uploads |

---

## 5. External Database Integration

### 5.1 SQL Connector (Debezium CDC)

```
External DB (PG/MySQL/MSSQL) → Debezium Connector → Event Hubs (cdc-{source}) 
→ CDC Consumer → Vectorizer → Qdrant (external.sql.{source})
```

```yaml
cdc:
  debezium:
    enabled: true
    eventhub_topic_prefix: cdc-
    sources:
      servicenow:
        host: servicenow-db.internal
        database: servicenow_prod
        tables:
          - cmdb_ci
          - incident
          - change_request
        columns:
          cmdb_ci: [sys_id, name, serial_number, category, location]
```

### 5.2 NoSQL Connector (Change Streams)

```
MongoDB Replica Set → Change Stream → Event Hubs (cdc-mongodb-{collection})
→ Vectorizer → Qdrant (external.nosql.mongodb.{collection})
```

```yaml
nosql:
  mongodb:
    enabled: true
    connection_string: ${MONGODB_URI}
    collections:
      - name: incidents
        vectorize: true
        projection: { _id: 1, title: 1, description: 1, severity: 1 }
  cosmos:
    enabled: true
    database: magenta
    containers:
      - name: mission_state
        vectorize: true
```

### 5.3 Schema Discovery

On first connection, the mesh auto-discovers table/collection schemas:

```python
# Example: SQL table → data product registration
{
  "product": "external.sql.servicenow.cmdb_ci",
  "schema": {
    "sys_id": {"type": "string", "pk": True},
    "name": {"type": "string", "embed": True},
    "serial_number": {"type": "string"},
    "category": {"type": "string", "filter": True},
    "location": {"type": "string", "filter": True}
  },
  "embed_columns": ["name", "description"],
  "filter_columns": ["category", "location", "status"]
}
```

---

## 6. Agent Memory & Context Integration

> **Superseded by**: ADR-018 (LLM-RAG Hybrid Memory Architecture) — this section reflects the updated dual-path design with tier-based token budgets, explicit multi-tenancy, and hybrid injection strategy.

### 6.1 Memory Types

| Memory | Backing Store | Vector Collection | Injection | Query Pattern |
|---|---|---|---|---|
| **Episodic** | Qdrant `mem_episodic` | `(agent_role, mission_id, tenant_id, turn_number) → embedding` | **Auto** (every turn, turn 2+) | "What did the triage agent do in mission X?" |
| **Semantic** | Qdrant `mem_semantic` | `(text, tenant_id, tags) → embedding` | **On-demand** via `memory.search_semantic` tool | "Find playbooks for ransomware containment" |
| **Procedural** | Qdrant `mem_procedural` | `(tool_name, parameters_hash, tenant_id) → embedding` | **On-demand** via `memory.search_procedures` tool | "How was disk isolation invoked last time?" |

### 6.2 Dual-Path Memory Architecture (ADR-018)

Agents use two concurrent paths for memory:

| Path | When | Latency Budget | Purpose |
|------|------|----------------|---------|
| **LLM Route** | Every agent turn | < 2s (speed tier) | Reasoning, tool selection, decision-making |
| **RAG Path** | Pre-inference (auto episodic) + on-demand (semantic/procedural) | < 200ms cached, < 500ms cold | Historical grounding, pattern matching |

**Config**: `agent.memory.pre_turn_rag.enabled` (default: `true` for episodic)

### 6.3 Context Injection Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│  AGENT TURN (n ≥ 2)                                                     │
│                                                                          │
│  1. PRE-TURN RAG (auto episodic)                                         │
│     ├─ memory_mcp.search_episodes(                                       │
│     │     query=current_alert_summary,                                   │
│     │     agent_role=self.config.role,                                   │
│     │     mission_id=mission.mission_id,                                 │
│     │     tenant_id=self.config.tenant_id,                               │
│     │     top_k=3                                                        │
│     │   )                                                                │
│     ├─ Truncate to tier budget (1000/3000/500 tokens)                    │
│     └─ Inject into system_prompt as "Relevant Past Decisions"            │
│                                                                          │
│  2. LLM INFERENCE                                                        │
│     ├─ llm_generate(                                                     │
│     │     prompt=system_prompt + user_context,                           │
│     │     tier=self._resolve_task_type(),                                │
│     │     temperature=0.2                                                │
│     │   )                                                                │
│     └─ Response: content + tool_calls[]                                  │
│                                                                          │
│  3. TOOL EXECUTION (if tool_calls)                                       │
│     ├─ Execute tool (sentinel, entra, defender, etc.)                    │
│     └─ Result: action_outcome                                           │
│                                                                          │
│  4. POST-TURN WRITE (auto episodic)                                      │
│     ├─ log_activity(mission, action, status)                             │
│     │   └─ memory_mcp.write_episode(                                     │
│     │         agent_role=role,                                           │
│     │         mission_id=mission_id,                                     │
│     │         turn_number=turn_count,                                    │
│     │         text="Action: {action} | Status: {status}",                │
│     │         correlation_id=correlation_id,                             │
│     │         tenant_id=tenant_id                                        │
│     │       )                                                            │
│     └─ VectorizationPipeline.ingest() → Qdrant mem_episodic             │
│                                                                          │
│  5. OPTIONAL SEMANTIC/PROCEDURAL (tool-call triggered)                   │
│     ├─ If agent calls memory.search_semantic → retrieve policy           │
│     ├─ If agent calls memory.search_procedures → tool patterns          │
│     └─ Results injected into next turn context                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Context Token Budget (Dynamic by Tier — ADR-018)

| Tier | Budget (tokens) | Use Case |
|------|-----------------|----------|
| `speed` | 1,000 | Real-time containment, triage |
| `reasoning` | 3,000 | Investigation, swarm manager |
| `cost_save` | 500 | Audit, reporting |

**Allocation within tier budget**:

| Allocation | % of Tier Budget | Notes |
|------------|------------------|-------|
| System prompt | 30% | Role, tools, guardrails |
| Retrieved context (RAG) | 40% | Top-3 results from memory |
| Conversation history | 20% | Last 5 turns |
| Current query/alert | 10% | Raw input |

### 6.5 Multi-Tenancy (ADR-018)

All memory payloads include `tenant_id` field:

```json
{
  "agent_role": "triage",
  "mission_id": "M123",
  "tenant_id": "acme-corp",
  "turn_number": 3,
  "memory_type": "episodic",
  "provenance": {
    "pipeline_step": "memory.write_episode",
    "input_hash": "a1b2c3d4..."
  }
}
```

**Query filter**: `filter={"must": [{"key": "tenant_id", "match": {"value": tenant_id}}]}`

Default `tenant_id`: `"default"` (single-tenant deployments).

### 6.6 Embedding Cache (Redis — ADR-018)

| Parameter | Value |
|-----------|-------|
| TTL | 24 hours |
| Key format | `embed:{model}:{text_sha256[:16]}` |
| Max entries | 100,000 |
| Eviction | LRU |

Cache hit: skip OLLAMA embed call. Cache miss: embed + store.

---

## 7. Query Federation

### 7.1 Unified Query Interface

```python
POST /api/v1/mesh/query
{
  "query": "critical alerts involving user pablo.garcia",
  "products": ["siem.alerts", "identity.directory", "agent.memory.episodic"],
  "filters": {"severity": ["high", "critical"]},
  "top_k": 10,
  "hybrid": true,          # dense + sparse fusion
  "explain": false         # return scoring breakdown
}
```

Response:

```json
{
  "results": [
    {
      "product": "siem.alerts",
      "score": 0.91,
      "payload": {
        "incident_id": "inc-8932",
        "title": "User account anomalous sign-in",
        "severity": "critical",
        "entities": ["pablo.garcia@contoso.com"],
        "timestamp": "2026-06-13T10:30:00Z"
      }
    },
    {
      "product": "identity.directory",
      "score": 0.85,
      "payload": {
        "display_name": "Pablo Garcia",
        "department": "Engineering",
        "roles": ["admin"]
      }
    }
  ],
  "federation": {
    "cross_product": true,
    "matched_entities": ["pablo.garcia@contoso.com"],
    "latency_ms": 47
  }
}
```

### 7.2 Cross-Product Join

The mesh correlates across products via `correlation_id`, `entity`, or `timestamp`:

| Join Dimension | Products | Strategy |
|---|---|---|
| `correlation_id` | siem.alerts ↔ soar.actions ↔ agent.memory.episodic | Exact match on UUID |
| `entity` (user/host/IP) | siem.alerts ↔ identity.directory ↔ threat.intel.iocs | Entity resolution + fuzzy |
| `timestamp` | siem.alerts ↔ external.nosql.mission_state | Time-windowed join |

---

## 8. Governance

### 8.1 Schema Registry

Each data product publishes its schema to a central registry:

```json
{
  "product": "siem.alerts",
  "version": "1.0.0",
  "schema": {
    "type": "object",
    "properties": {
      "incident_id": {"type": "string", "format": "uuid"},
      "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
      "title": {"type": "string"},
      "mitre_tactics": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["incident_id", "severity"]
  },
  "sla": {
    "freshness": "30s",
    "completeness": "0.99",
    "accuracy": "0.95"
  }
}
```

### 8.2 Data Quality

| Metric | Threshold | Alert |
|---|---|---|
| Embedding throughput | < 10 docs/s | Warning |
| Vector search p99 latency | > 200 ms | Warning |
| CDC consumer lag | > 60 s | Warning → Page |
| Schema conformance | < 99% | Page |
| Index size | > 80% disk | Warning |

### 8.3 Access Control

```
┌────────────────────────────────────┐
│           AGENT ROLE                │
│  triage_agent                       │
├────────────────────────────────────┤
│  CAN QUERY                          │
│  ├── siem.alerts                    │
│  ├── identity.directory             │
│  ├── threat.intel.iocs              │
│  ├── agent.memory.episodic          │
│  └── agent.memory.semantic          │
├────────────────────────────────────┤
│  CANNOT QUERY                       │
│  ├── external.sql.servicenow        │
│  └── external.nosql.*               │
├────────────────────────────────────┤
│  CAN INGEST                         │
│  └── agent.memory.episodic          │
└────────────────────────────────────┘
```

---

## 9. Technology Stack (Phase 1)

| Component | Technology | Purpose |
|---|---|---|
| Vector store | Qdrant 1.x | Multi-vector, payload filtering, GRPC |
| Embedder | OLLAMA (nomic-embed-text / bge-m3) | Text → vector |
| Sparse index | Tantivy (embedded via mesh-gateway) | BM25 keyword search |
| Metadata cache | Redis 7.x | Hot filter values, embedding cache |
| CDC connector | Debezium 2.x / Event Hubs Kafka | External SQL CDC |
| NoSQL streams | MongoDB Change Streams / Cosmos Change Feed | NoSQL CDC |
| Mesh gateway | FastAPI (extends existing `api/` layer) | Query federation + ingestion |
| Orchestration | Apache Airflow (optional) | Batch embedding jobs |
| Schema registry | JSON Schema + Git | Version-controlled schemas |

---

## 10. Phased Buildout

### Phase 1 (Now) — Core Vectorization + External DBs

- [x] Architecture documented
- [x] Docker Compose for local dev
- [x] K8s manifests for Qdrant, OLLAMA, mesh-gateway
- [ ] Telemetry collection plane (ADR-011): raw-logs topic, Log Normalizer, ingest API
- [ ] Vectorization pipeline: chunker → embedder → indexer
- [ ] CDC connectors for external SQL (Debezium)
- [ ] CDC connectors for NoSQL (MongoDB, Cosmos)
- [ ] Mesh gateway: `/query`, `/ingest`, `/products`, `/health`
- [ ] Agent memory integration: episodic + semantic writes
- [ ] Endpoint/cloud data product ingestion in mesh catalog

### Phase 2 (Next) — Analytics + Binary

- [ ] Analytics resource integration (OLAP, data warehouse)
- [ ] Blob/binary ingestion (PDFs, PCAPs, forensic images)
- [ ] Multi-modal embedding (text + image)
- [ ] Materialized vector views for common agent patterns

### Phase 3 (Future) — Federated Governance

- [ ] Data lineage via OpenLineage
- [ ] Cost attribution per data product query
- [ ] Auto-schema evolution with diff review
- [ ] Agent-to-agent data product marketplace
