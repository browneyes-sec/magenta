# Magenta ASOAR — RAG/LLM Integration Assessment

**Date:** 2026-06-20
**Scope:** Full-stack integration of LLM, RAG, agent, API, data, and web layers
**Assessment Type:** Engineering & Architectural Finesse

---

## Executive Summary

Magenta ASOAR implements a **5-layer integration architecture** connecting LLM inference, vectorized memory, agent orchestration, operator control plane, and data infrastructure. The integration is **architecturally sound** with **2 critical gaps** and **5 refinement opportunities** identified.

| Layer | Integration Score | Status |
|-------|-------------------|--------|
| LLM/Model Routing | 8/10 | Good — tiered fallback works |
| RAG/Memory Pipeline | 9/10 | Excellent — hybrid RRF proven |
| Agent Integration | 7/10 | Good — pre-turn RAG wired, gaps in log_activity |
| API/Web Layer | 6/10 | Fair — auth middleware incomplete |
| Data Infrastructure | 8/10 | Good — Qdrant+OLLAMA healthy |
| **Overall** | **7.6/10** | **Solid foundation, refinements needed** |

---

## Layer 1: LLM/Model Routing

### Architecture

```
Agent Request
    │
    ▼
LLMGateway.route()
    │
    ├──→ PolicyEngine.evaluate()  ────→ PolicyDecision
    │        │
    │        ├── sensitivity=high → Ollama only (no egress)
    │        ├── sensitivity=medium → Ollama preferred
    │        └── sensitivity=low → any provider
    │
    ├──→ RedactionLayer.apply()  ────→ PII scrubbed
    │
    ├──→ CircuitBreaker.is_open()  ────→ fallback if degraded
    │
    ├──→ TokenBucket.consume()  ────→ rate limiting
    │
    ├──→ SemanticCache.get()  ────→ cache hit → return
    │
    └──→ ModelRouter.route(tier)
             │
             ├── speed → qwen2.5:7b, mistral:7b, deepseek-r1:7b
             ├── reasoning → mixtral:8x7b, qwen2.5:32b
             └── cost_save → openrouter, gemini, groq
```

### Strengths
- **Sensitivity-based routing**: HIGH sensitivity locks to Ollama (zero egress) — security-critical
- **3-tier fallback chain**: speed → reasoning → cost_save with per-tier latency thresholds
- **Circuit breaker**: Auto-fallback on provider failure
- **Semantic cache**: 92% similarity threshold reduces redundant calls
- **Audit trail**: Full request/response logging with risk scoring

### Gaps
| Gap | Impact | Fix |
|-----|--------|-----|
| `SemanticCache._similarity()` always returns 1.0 (line 60) | Cache never hits semantic matches | Implement cosine similarity on request hashes |
| No model health probing on startup | First request fails if provider down | Add `ping_all()` in lifespan |
| `ModelRouter` shuffles clients randomly | No latency-aware routing | Add weighted selection based on recent p50 |

---

## Layer 2: RAG/Memory Pipeline

### Architecture

```
Memory Write
    │
    ▼
MemoryMCPServer.write_episode()
    │
    ▼
VectorizationPipeline.ingest()
    │
    ├──→ SemanticChunker.chunk()  ────→ 512-token chunks, 64 overlap
    │
    ├──→ OllamaEmbedder.embed()  ────→ nomic-embed-text (768-dim)
    │
    ├──→ QdrantIndexer.upsert()  ────→ mem_episodic/semantic/procedural
    │
    └──→ TantivyBM25Sidecar.add_document()  ────→ sparse index


Memory Search
    │
    ▼
VectorizationPipeline.search()
    │
    ├──→ OllamaEmbedder.embed_single(query)
    │
    ├──→ QdrantIndexer.search()  ────→ dense vector results
    │
    ├──→ BM25Sidecar.search()  ────→ sparse lexical results
    │
    └──→ _rrf_fusion(k=60)  ────→ Reciprocal Rank Fusion
```

### Strengths
- **Hybrid search**: Dense (Qdrant) + Sparse (BM25) via RRF — industry best practice
- **Semantic chunking**: Sentence-boundary aware, 512 tokens with 64 overlap
- **Provenance tracking**: Input hashes, pipeline steps, lineage integration
- **3 memory types**: Episodic (decisions), Semantic (knowledge), Procedural (tools)
- **OTel tracing**: Full span instrumentation on writes and searches

### Gaps
| Gap | Impact | Fix |
|-----|--------|-----|
| BM25 sidecar lost on restart (in-memory) | Search quality degrades after reboot | Persist to disk or rebuild from Qdrant payloads |
| No embedding cache TTL | Embeddings recomputed on every write | Add 24h cache in OllamaEmbedder |
| `pipeline.search()` returns empty on embed failure | Silent failure, no error propagation | Log warning, return partial results |

---

## Layer 3: Agent Integration

### Architecture

```
BaseAgent.process(mission, context)
    │
    ├──→ turn_count += 1
    │
    ├──→ retrieve_context()  ────→ RAG injection (ADR-018)
    │        │
    │        ├── turn_count <= 1 → skip (no history)
    │        │
    │        └── memory_mcp.search_episodes()
    │             └── context["rag_context"] = result
    │
    ├──→ _process_impl(mission, context)
    │        │
    │        ├── TriageAgent → context["rag_context"] in prompt
    │        ├── EnrichAgent → context["rag_context"] in prompt
    │        ├── ContainAgent → context["rag_context"] in prompt
    │        ├── InvestigateAgent → context["rag_context"] in prompt
    │        ├── ComplianceAgent → context["rag_context"] in prompt
    │        └── ReportAgent → context["rag_context"] in prompt
    │
    └──→ log_activity()  ────→ memory_mcp.write_episode()
```

### Strengths
- **Pre-turn RAG**: `retrieve_context()` wired in `BaseAgent.process()` — automatic for all agents
- **Tier-aware budgets**: speed=1000, reasoning=3000, cost_save=500 tokens
- **Turn gating**: Skips RAG on turn 1 (no history to retrieve)
- **Tenant propagation**: `tenant_id` flows from context through to memory writes
- **Fallback-safe**: RAG failures log warning, don't block agent execution

### Gaps
| Gap | Impact | Fix |
|-----|--------|-----|
| `log_activity()` not called in `BaseAgent.process()` | Agent decisions not automatically logged | Add post-turn hook in `process()` |
| `retrieve_context()` only searches episodic | No semantic/procedural context enrichment | Add multi-collection search |
| No RAG context relevance scoring | Low-quality results pollute prompts | Add score threshold (e.g., >0.3) |
| `task_type` fallback to "generic" | Wrong token budget if not set | Set per-agent in config |

---

## Layer 4: API/Web Layer

### Architecture

```
Open WebUI (port 3000)
    │
    ├──→ Pipelines (port 9099)
    │        │
    │        └──→ magenta-api:8000
    │                 │
    │                 ├──→ /api/v1/mesh/memory/* (6 endpoints)
    │                 ├──→ /api/v1/agents/*
    │                 ├──→ /api/v1/missions/*
    │                 └──→ /mcp/*
    │
    ├──→ MCPO (port 8001) ────→ MCP servers
    │
    └──→ OLLAMA (port 11434) ────→ LLM inference
```

### Strengths
- **Governed access**: All routes through `magenta-api:8000` — no bypass
- **CORS locked**: Origins restricted to localhost:3000, localhost:8000
- **Memory endpoints**: 6 HTTP endpoints with Pydantic validation
- **Tenant middleware**: `get_tenant_id()` dependency on all memory routes
- **Startup auto-provision**: Collections created on API boot

### Gaps
| Gap | Impact | Fix |
|-----|--------|-----|
| `get_tenant_id()` always returns "default" | Multi-tenant isolation not enforced | Decode JWT claims for tenant |
| No API key validation on memory endpoints | Unauthenticated writes possible | Add `Depends(validate_auth)` |
| Pipeline tools bypass auth | Direct HTTP to API without tokens | Add API key header in pipeline |
| Open WebUI `ENABLE_SIGNUP: "false"` | No user management | Add Entra ID OIDC integration |

---

## Layer 5: Data Infrastructure

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Data Layer                            │
├─────────────┬─────────────┬─────────────┬───────────────┤
│   Qdrant    │   OLLAMA    │    Redis    │   Open WebUI  │
│  (6333)     │  (11434)    │   (6379)    │   (3000)      │
│             │             │             │               │
│ mem_episodic│ nomic-embed │ session     │ operator UX   │
│ mem_semantic│ qwen2.5:0.5b│ cache       │ chat history  │
│ mem_proc.   │             │ queue       │ pipeline conf │
└─────────────┴─────────────┴─────────────┴───────────────┘
```

### Strengths
- **Qdrant**: 3 collections, 768-dim cosine, 39+ vectors — healthy
- **OLLAMA**: nomic-embed-text (768-dim) for embeddings, qwen2.5 for inference
- **Redis**: Session storage, rate limiting, policy persistence
- **Health checks**: All services have healthcheck configs
- **Memory limits**: MVS stack fits in ~1.5GB total

### Gaps
| Gap | Impact | Fix |
|-----|--------|-----|
| No Qdrant backup automation | Data loss on crash | Add cron-based snapshot |
| OLLAMA single model loaded | Cold start on model switch | Pre-load primary models |
| Redis no persistence config | Data loss on restart | Add AOF persistence |
| No Qdrant replication | Single point of failure | Add 1 replica in prod |

---

## Integration Flow Matrix

| From → To | Protocol | Auth | Error Handling | Status |
|-----------|----------|------|----------------|--------|
| Agent → LLM Gateway | In-process | Sensitivity gate | Circuit breaker | ✅ |
| Agent → Memory MCP | In-process | None (internal) | Try/catch, log | ✅ |
| Memory MCP → Pipeline | In-process | None | Try/catch | ✅ |
| Pipeline → OLLAMA | HTTP | None | Retry, timeout | ✅ |
| Pipeline → Qdrant | gRPC/HTTP | None | Try/catch | ✅ |
| API → Memory MCP | In-process | None | Try/catch | ✅ |
| Pipeline → API | HTTP | API key | HTTP errors | ⚠️ |
| Open WebUI → Pipeline | HTTP | API key | Pipeline errors | ✅ |
| Open WebUI → OLLAMA | HTTP | None | Timeout | ✅ |
| MCPO → API | HTTP | None | HTTP errors | ⚠️ |

---

## Critical Fixes (P0)

### 1. Semantic Cache Broken
**File:** `magenta/gateway/cache.py:58-60`
**Issue:** `_similarity()` always returns 1.0 — semantic matching never works
**Fix:** Implement actual cosine similarity using embeddings or request hash comparison

### 2. log_activity() Not Auto-Triggered
**File:** `magenta/core/agent.py`
**Issue:** `log_activity()` exists in LLMAgent but not called in `BaseAgent.process()`
**Fix:** Add post-turn hook to automatically log agent decisions

---

## Refinement Opportunities (P1)

### 3. BM25 Persistence
**Issue:** BM25 sidecar is in-memory — lost on restart
**Fix:** Persist to disk via Tantivy or rebuild from Qdrant payloads on startup

### 4. Embedding Cache TTL
**Issue:** Same text re-embeds on every write
**Fix:** Add 24h TTL cache in OllamaEmbedder for repeated content

### 5. JWT Tenant Extraction
**Issue:** `get_tenant_id()` returns hardcoded "default"
**Fix:** Decode JWT claims to extract actual tenant_id for multi-tenant isolation

---

## Validation Commands

```bash
# Health check
python scripts/mesh/validate_memory.py --env dev --write-test

# RAG accuracy
python scripts/mesh/seed_eval_data.py --env dev --clear-first
python scripts/mesh/rag_accuracy.py --env dev

# Load test
python scripts/mesh/load_test.py --env dev --writes 100 --searches 100

# Backup/restore
python scripts/mesh/test_backup_restore.py --env dev --cleanup
```

---

## Conclusion

Magenta ASOAR has a **well-architected integration layer** with:
- Sensitivity-based LLM routing (security-first)
- Hybrid RAG with proven RRF fusion
- Pre-turn RAG wired into all 7 agents
- Open WebUI operator control plane with governed access

The **2 critical fixes** (cache similarity, auto-logging) are small changes with high impact. The **5 refinements** improve production-readiness but don't block MVS validation.

**Recommendation:** Fix P0 items, then proceed to Phase 2 (load testing, chaos scenarios).
