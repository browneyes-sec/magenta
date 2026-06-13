# Vector Store Architecture & Sizing

## Component Overview

Magenta uses vector stores for:

- **Semantic search** over past incidents, playbooks, and agent decisions
- **Similarity-based triage** — match incoming alerts to historical patterns
- **RAG pipelines** — retrieve relevant context before agent LLM calls
- **Agent memory** — episodic memory across missions

Current implementation uses ChromaDB (dev) with provision for production backends (Qdrant, pgvector, Elasticsearch vector fields).

## Embedding Model

```yaml
embeddings:
  provider: ollama
  model: nomic-embed-text:v1.5   # 768-dim, ~1.5 GB VRAM
  dimension: 768
  batch_size: 32
```

| Embedding Model | Dimensions | VRAM | Quality |
|---|---|---|---|
| `nomic-embed-text:v1.5` | 768 | ~1.5 GB | Good |
| `bge-m3` | 1024 | ~2.5 GB | Excellent |
| `all-MiniLM-L6-v2` | 384 | ~0.5 GB | Adequate |

## Index Configuration

### Dev (ChromaDB)

```python
from chromadb import PersistentClient
client = PersistentClient(path="data/vectorstore/")
collection = client.get_or_create_collection(
    name="magenta-knowledge",
    metadata={"hnsw:space": "cosine", "hnsw:construction_ef": 100},
)
```

### Production (Qdrant)

```yaml
vector_store:
  backend: qdrant
  host: localhost
  port: 6333
  prefer_grpc: true
  collections:
    agent_memory:
      vectors:
        size: 768
        distance: Cosine
      optimizers:
        default_segment_number: 2
        memmap_threshold_kb: 20000
    incident_patterns:
      vectors:
        size: 768
        distance: Cosine
      hnsw_config:
        m: 16
        ef_construct: 200
```

### Production (pgvector)

```sql
CREATE EXTENSION vector;
CREATE TABLE incident_embeddings (
    id UUID PRIMARY KEY,
    embedding vector(768),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON incident_embeddings USING hnsw (embedding vector_cosine_ops);
```

## Sizing

| Corpus | Docs | Embeddings | Storage (768-dim, FP32) |
|---|---|---|---|
| Past incidents (30 days) | 10,000 | 30,000 | ~90 MB |
| Past incidents (1 year) | 120,000 | 360,000 | ~1.1 GB |
| Knowledge base | 5,000 | 5,000 | ~15 MB |
| Agent decisions | 50,000 | 50,000 | ~150 MB |
| Playbooks + rules | 200 | 2,000 | ~6 MB |
| **Total (1 year)** | | **~417,000** | **~1.3 GB** |

## RAG Pipeline Sizing

```yaml
rag:
  retrieval:
    top_k: 5
    score_threshold: 0.75
  context_window: 4096       # tokens to pass to LLM
  max_context_docs: 3        # docs per agent turn
```

At 5 retrieved docs × 800 tokens/doc = 4,000 tokens of context. Add system prompt (1,000 tokens) and user query (500 tokens) = approximately 5,500 tokens per agent turn within a 4K-8K context window.

## Monitoring

| Metric | Alert |
|---|---|
| Query latency p99 > 200 ms | Warning |
| Index size > 80% of disk | Warning |
| Embedding queue depth > 50 | Warning |
| Recall@5 < 70% | Investigate index health |
