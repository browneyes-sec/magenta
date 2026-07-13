# Magenta Data Mesh

Unified vectorized semantic layer for agent memory, context, and multi-source query federation.

## What It Is

The data mesh ingests, vectorizes, and indexes data from every Magenta source domain — SIEM alerts, SOAR actions, external databases, NoSQL stores, identity directories, and threat intel — into a single queryable fabric. Agents consume the mesh instead of accessing raw sources.

## Quickstart

```bash
# Start the local mesh stack
docker compose -f data/deploy/docker-compose.yml up -d

# Verify health
curl http://localhost:8000/api/v1/mesh/health

# List available data products
curl http://localhost:8000/api/v1/mesh/products

# Ingest a document
curl -X POST http://localhost:8000/api/v1/mesh/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "product": "agent.memory.semantic",
    "documents": [
      {"id": "doc-001", "text": "Ransomware containment playbook v2...", "metadata": {"tags": ["ransomware"]}}
    ]
  }'

# Query across products
curl -X POST http://localhost:8000/api/v1/mesh/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "ransomware containment steps",
    "products": ["agent.memory.semantic", "siem.alerts"],
    "top_k": 5
  }'
```

## Directory Layout

```
data/
├── readme.md                   ← This file
├── deploy/
│   ├── docker-compose.yml      ← Local dev stack
│   └── kubernetes/             ← Production K8s manifests
└── vectorstore/                ← Runtime: local ChromaDB (dev)
└── sqlite/                     ← Runtime: local SQLite (dev)
```

## Architecture

See [`architecture/data-mesh/readme.md`](../architecture/data-mesh/readme.md) for the full design.

## Data Products

| Product | Source | Vector Index |
|---|---|---|
| `siem.alerts` | Sentinel / Splunk incidents | `siem_alerts` |
| `soar.actions` | Splunk SOAR audit | `soar_actions` |
| `external.sql.*` | External SQL DBs (CDC) | `ext_sql_{source}` |
| `external.nosql.*` | MongoDB / Cosmos DB (CDC) | `ext_nosql_{source}` |
| `identity.directory` | Entra ID | `identity_dir` |
| `threat.intel.iocs` | VT / Shodan / OTX | `threat_iocs` |
| `agent.memory.episodic` | Mission transcripts | `mem_episodic` |
| `agent.memory.semantic` | KB, playbooks, runbooks | `mem_semantic` |
| `agent.memory.procedural` | Tool usage patterns | `mem_procedural` |

## API Endpoints

All mesh endpoints are at `/api/v1/mesh/*`:

| Method | Path | Purpose |
|---|---|---|
| POST | `/mesh/query` | Hybrid search across data products |
| POST | `/mesh/ingest` | Push documents for vectorization |
| GET | `/mesh/products` | List available data products |
| GET | `/mesh/health` | Component health and latency |

## Dependencies

- **Qdrant** — vector database
- **OLLAMA** — embedding model inference
- **Redis** — metadata cache, embedding cache
- **Debezium** — CDC for external SQL databases
- **FastAPI** — mesh gateway (extends existing API)
