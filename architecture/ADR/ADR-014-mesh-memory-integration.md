# ADR-014: Mesh Gateway Memory Integration & Embedding Model Upgrade

**Status:** Accepted  
**Date:** 2026-06-16  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture, AI/ML Engineering, Data Engineering  

---

## Context

The Magenta ASOAR platform has a vectorized data mesh (ADR-010) with Qdrant, OLLAMA, and Redis, but three critical gaps prevent production readiness:

1. **No agent memory persistence** — `LLMAgent.log_activity()` is a stub returning `None`. Zero agent actions persist to any registry, Qdrant, or Data Lake. Every agent starts every mission with zero memory of prior incidents.

2. **No memory MCP integration** — The mesh gateway exists but has no MCP tools for episodic, semantic, or procedural memory operations. Agents cannot write or retrieve memory through the established MCP/SOA architecture.

3. **Suboptimal embedding model** — ADR-010 specified `nomic-embed-text:v1.5` (768-dim) as the default, but security telemetry (SIEM alerts, SOAR playbooks, threat intel) contains domain-specific terminology (MITRE ATT&CK IDs, CVE references, network IOCs) that general embedding models underperform on. The data mesh spec (§4.2) recommends `bge-m3` (1024-dim) for threat intel and complex playbooks.

The DTP (Design Technical Plan) acceptance criteria require:
- Every source-to-action path persists canonical `automation.activity` records
- Every agent uses mesh-mediated retrieval before model inference
- All memory/context retrieval goes through `/api/v1/mesh/*`

---

## Decision

### 1. Memory MCP Server (integrated into mesh gateway)

Add a `MemoryMCPServer` class to `magenta/mesh/memory.py` with six MCP tools:

| Tool | Collection | Purpose |
|---|---|---|
| `memory.write_episode` | `mem_episodic` | Write mission transcripts, agent decisions |
| `memory.search_episodes` | `mem_episodic` | Search past agent decisions |
| `memory.write_semantic` | `mem_semantic` | Write playbooks, runbooks, policies |
| `memory.search_semantic` | `mem_semantic` | Search reusable knowledge |
| `memory.write_procedure` | `mem_procedural` | Write tool invocation patterns |
| `memory.search_procedures` | `mem_procedural` | Search tool usage patterns |

**Why integrated into mesh gateway (not separate service):**
- Mesh gateway already owns Qdrant, OLLAMA, and Redis connections.
- Avoids extra network hop and service discovery complexity.
- Memory operations are a subset of mesh operations (ingest/search).
- Follows the MCP service catalog pattern (one service, multiple tool sets).

### 2. LLMAgent.log_activity() Wiring

Replace the stub in `magenta/agents/base.py` with a real implementation that:
- Creates an `AutomationActivity` record (existing logic, unchanged).
- Calls `memory_mcp.write_episode()` to persist to Qdrant `mem_episodic`.
- Catches exceptions gracefully (memory write failure does not block agent execution).

### 3. Embedding Model Upgrade

Upgrade from `nomic-embed-text:v1.5` (768-dim) to `bge-m3` (1024-dim):

| Parameter | Old Value | New Value |
|---|---|---|
| `MESH__OLLAMA_MODEL` | `nomic-embed-text:v1.5` | `bge-m3` |
| `MESH__EMBEDDING_DIMENSION` | `768` | `1024` |
| Qdrant vector size | 768 | 1024 |
| HNSW `m` | 16 | 16 (unchanged) |
| HNSW `ef_construct` | 200 | 200 (unchanged) |

**Why bge-m3:**
- Better performance on domain-specific security terminology.
- 1024-dim provides higher semantic fidelity for complex queries.
- Supports multilingual content (relevant for global SOC operations).
- Recommended by data mesh spec (§4.2) for threat intel and complex playbooks.

### 4. Qdrant Collection Auto-Create

Mesh gateway creates all collections on startup if `MESH__COLLECTIONS_AUTO_CREATE=true`:
- Collections: `siem_alerts`, `mem_episodic`, `mem_semantic`, `mem_procedural`, `endpoint_windows`, `endpoint_linux`, `cloud_azure`, `cloud_aws`, `cloud_gcp`, `customer_custom`
- HNSW config: `m=16`, `ef_construct=200` per data mesh spec (§4.3)
- Optimizers: `default_segment_number=2`, `memmap_threshold_kb=20000`

---

## Consequences

### Positive
- Agents gain persistent memory across missions (episodic, semantic, procedural).
- Memory operations go through the established MCP/SOA architecture.
- `bge-m3` improves retrieval quality for security-specific queries.
- Auto-create collections eliminates manual Qdrant setup.
- All memory writes flow through the vectorization pipeline (chunk → embed → index).

### Negative
- `bge-m3` requires more RAM (~4GB vs ~2GB for nomic-embed-text) — drives node pool sizing.
- 1024-dim vectors consume ~33% more storage than 768-dim.
- Existing 768-dim indices require re-indexing if migrating from nomic-embed-text.

### Risks
- OLLAMA model pull timeout on slow networks — mitigated by init container with retry logic.
- Qdrant collection creation race condition (multiple gateway replicas) — mitigated by idempotent create (skip if exists).

---

## Compliance

| Provision | ADR-010 (Data Mesh) | ADR-011 (Telemetry) | DTP §2.3 | DTP §4.2 |
|---|---|---|---|---|
| Memory MCP tools | Extends mesh gateway | — | Mesh gateway routes | Memory architecture |
| bge-m3 default | Updates §4.2 | — | — | Embedding config |
| Auto-create collections | Extends §4.3 | — | — | Qdrant config |
| LLMAgent.log_activity() wiring | — | — | Registry persistence | Memory writes |

---

## Implementation

Files created/modified:
- `magenta/mesh/__init__.py` — module exports
- `magenta/mesh/config.py` — MeshConfig dataclass (env-based)
- `magenta/mesh/collections.py` — Qdrant collection management + HNSW configs
- `magenta/mesh/pipeline.py` — VectorizationPipeline (chunker → embedder → indexer)
- `magenta/mesh/memory.py` — MemoryMCPServer (6 MCP tools)
- `magenta/mesh/gateway.py` — MeshGateway (query, ingest, products, health)
- `magenta/api/routes/mesh.py` — FastAPI routes for /api/v1/mesh/*
- `magenta/agents/base.py` — LLMAgent.log_activity() wired to memory MCP
- `magenta/models/router.py` — shuffle bug fix + sensitivity routing
- `data/deploy/kubernetes/mesh-gateway.yaml` — bge-m3, 1024-dim, collection init
- `data/deploy/kubernetes/vector-store-statefulset.yaml` — collection config init container
- `data/deploy/kubernetes/qdrant-collection-configs.yaml` — HNSW configs per collection
- `data/deploy/kubernetes/mesh-config.yaml` — gateway config
- `data/deploy/docker-compose.yml` — bge-m3, 1024-dim for local dev
- `soa/terraform/modules/data/main.tf` — Terraform data plane module

---

## Notes

- The mesh gateway is the single integration point for all memory operations — no separate memory service.
- Memory writes are fire-and-forget from the agent's perspective (non-blocking).
- The `embed_single` method in OllamaEmbedder handles query embedding for search.
- Collection configs are defined in both K8s ConfigMap and Python `collections.py` for consistency.
