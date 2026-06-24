# ADR-010: Vectorized Data Mesh Architecture

**Status:** Accepted  
**Date:** 2026-06-14  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture, AI/ML Engineering  

---

## Context

Magenta requires a data mesh layer that stores and queries vector embeddings for agent memory (episodic, semantic, procedural), supports hybrid search (vector + keyword + metadata filtering), integrates with external SQL/NoSQL databases via CDC, and provides a unified query API for agents. The architecture is documented in detail at `architecture/data-mesh/readme.md` (496 lines).

Six vector database options were evaluated: Qdrant, Pinecone, Weaviate, Milvus, Elasticsearch, and pgvector. The evaluation covered: self-hosted vs SaaS, gRPC support, filtering performance, embedding dimension limits, and cost at 10M+ vectors.

---

## Decision

Build the data mesh on a **self-hosted, open-source stack**:

| Component | Technology | Role | Port |
|---|---|---|---|
| **Vector Store** | Qdrant | ANN search, vector CRUD, payload filtering | 6333 (REST), 6334 (gRPC) |
| **Embedding Service** | OLLAMA (nomic-embed-text:v1.5) | Text → 768-dim vector embeddings | 11434 |
| **Metadata Cache** | Redis 7.4 | Payload caching, rate limiting, session state | 6379 |
| **Object Store** | MinIO | CDC state, schema registry, large blob storage | 9000 (API), 9001 (Console) |
| **Mesh Gateway** | FastAPI (Python) | Unified query/ingestion API, CDC orchestration | 8000 |

**Why Qdrant:**
- Self-hosted (no SaaS dependency), Apache 2.0 license.
- Native gRPC (lower latency than REST-based competitors like Weaviate).
- Advanced payload filtering (filter on any vector metadata without re-indexing).
- Built-in quantization (scalar/product) for memory-efficient vector storage.
- Multi-node clustering without external dependencies.

**Why OLLAMA over API-based embeddings:**
- No per-token costs — embeddings are free once the model is pulled.
- `nomic-embed-text:v1.5` produces 768-dim embeddings (good balance of quality vs storage).
- Same model can be used for local inference (edge deployment).
- OLLAMA runs as a sidecar in the mesh deployment.

---

## Consequences

### Positive
- Full control over data — no vector data leaves the deployment boundary.
- No per-query costs (vs Pinecone's $0.10/1M query units).
- Qdrant's payload filtering enables agent-specific memory retrieval without multiple collections.
- The stack runs in Docker Compose for dev and Kubernetes for prod — same images, different orchestrators.
- OLLAMA supports GPU acceleration (available when `compute-gpu` node pool is enabled).

### Negative
- Self-hosting means operational overhead (backups, scaling, monitoring) — not SaaS zero-ops.
- OLLAMA requires significant RAM (~8GB for nomic-embed-text) — drives node pool sizing.
- CDC integration requires Debezium (Kafka) for production SQL/NoSQL change capture — not yet implemented.
- 768-dim embeddings are < 1536-dim from OpenAI/text-embedding-3-small (slightly less semantic fidelity).

### Risks
- OLLAMA model availability on ARM64 (minikube on Apple Silicon) — mitigated by x86 emulation or AMD64 nodes.
- Qdrant version upgrades may change on-disk format — mitigated by testing upgrades in staging first.
- Redis as single point of failure for cache — mitigated by Redis Sentinel in production tfvars.

---

## Compliance

Enforced by:
- **Docker Compose**: `data/deploy/docker-compose.yml` — all 5 services configured and tested.
- **K8s manifests**: `data/deploy/kubernetes/` — Qdrant StatefulSet, OLLAMA Deployment, mesh-gateway Deployment, namespace.
- **Mesh API**: defined in `soa/services/mesh-service.toml` with MCP tool definitions.
- **Architecture doc**: `architecture/data-mesh/readme.md` — comprehensive pipeline documentation.
- **Kustomize**: `data/deploy/kubernetes/kustomization.yaml` — applied via `kubectl apply -k data/deploy/kubernetes/`.

---

## Notes

- The mesh gateway is deployed separately from the SOA services (in `magenta-mesh` namespace, not `magenta-soa`).
- External DB integration (Debezium CDC for SQL/NoSQL) is documented in the architecture doc but deferred to Sprint 5+.
- Embedding dimension is set to 768 everywhere (`MESH__EMBEDDING_DIMENSION: 768` in docker-compose.yml) — changing dimensions requires re-indexing all vectors.
