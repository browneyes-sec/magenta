# ADR-018: LLM-RAG Hybrid Memory Architecture

**Status:** Accepted  
**Date:** 2026-06-19  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture, AI/ML Engineering, SOC Operations  
**Supersedes:** ADR-010 §4 (agent memory retrieval), ADR-014 §2 (log_activity wiring)

---

## Context

Magenta has three foundational pieces for agent memory:
1. **ADR-010**: Vectorized data mesh (Qdrant + OLLAMA bge-m3 + Redis + MinIO)
2. **ADR-014**: Memory MCP Server (6 tools: write/search for episodic, semantic, procedural)
3. **LLMAgent.log_activity()**: Wired to `memory_mcp.write_episode()` in `magenta/agents/base.py`

**The gap**: No architectural decision governs *how agents use memory during inference*. Currently:
- Agents write memory (post-action) but never read it (pre-inference)
- No RAG injection point exists in the agent lifecycle
- No policy governs memory type selection, token budgets, or multi-tenancy
- Operator cannot query "how did we handle X before" through Open WebUI

This ADR establishes the dual-path memory architecture that grounds every agent turn in historical context.

---

## Decision

### 1. Dual-Path Architecture

| Path | When | Latency Budget | Purpose |
|------|------|----------------|---------|
| **LLM Route** | Every agent turn | < 2s (speed tier) | Reasoning, tool selection, decision-making |
| **RAG Path** | Pre-inference (auto episodic) + on-demand (semantic/procedural) | < 200ms cached, < 500ms cold | Historical grounding, pattern matching, policy lookup |

Both paths coexist. **LLM for reasoning, RAG for grounding.**

### 2. RAG Injection Strategy (Hybrid)

| Memory Type | Injection | Rationale |
|-------------|-----------|-----------|
| **Episodic** | Auto-injected before every turn (turn 2+) | Agent needs "what happened before" without asking |
| **Semantic** | On-demand via `memory.search_semantic` tool | Playbooks/runtimes are policy-driven, not always needed |
| **Procedural** | On-demand via `memory.search_procedures` tool | Tool patterns are situational |

**Config flag**: `agent.memory.pre_turn_rag.enabled` (default: `true` for episodic)

### 3. Context Token Budget (Dynamic by Tier)

| Tier | Budget (tokens) | Use Case |
|------|-----------------|----------|
| `speed` | 1,000 | Real-time containment, triage |
| `reasoning` | 3,000 | Investigation, swarm manager |
| `cost_save` | 500 | Audit, reporting |

Budget enforced in `LLMAgent.retrieve_context()`. Excess results truncated by relevance score.

### 4. Multi-Tenancy (Explicit)

All memory payloads include `tenant_id` field:
```json
{
  "agent_role": "triage",
  "mission_id": "M123",
  "tenant_id": "acme-corp",
  "turn_number": 3,
  "memory_type": "episodic"
}
```

Default `tenant_id`: `"default"` (single-tenant deployments).  
Query filters: `filter={"must": [{"key": "tenant_id", "match": {"value": tenant_id}}]}`

### 5. Embedding Cache (Redis)

| Parameter | Value |
|-----------|-------|
| TTL | 24 hours |
| Key format | `embed:{model}:{text_sha256[:16]}` |
| Max entries | 100,000 |
| Eviction | LRU |

---

## Agent Memory Lifecycle

```
Mission Start
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  AGENT TURN (n ≥ 2)                                            │
│                                                                 │
│  1. PRE-TURN RAG (auto episodic)                                │
│     ├─ memory_mcp.search_episodes(                              │
│     │     query=current_alert_summary,                          │
│     │     agent_role=self.config.role,                          │
│     │     mission_id=mission.mission_id,                        │
│     │     top_k=3                                               │
│     │   )                                                       │
│     ├─ Truncate to tier budget (1000/3000/500 tokens)           │
│     └─ Inject into system_prompt as "Relevant Past Decisions"   │
│                                                                 │
│  2. LLM INFERENCE                                               │
│     ├─ llm_generate(                                            │
│     │     prompt=system_prompt + user_context,                  │
│     │     tier=self._resolve_task_type(),                       │
│     │     temperature=0.2                                       │
│     │   )                                                       │
│     └─ Response: content + tool_calls[]                         │
│                                                                 │
│  3. TOOL EXECUTION (if tool_calls)                              │
│     ├─ Execute tool (sentinel, entra, defender, etc.)           │
│     └─ Result: action_outcome                                  │
│                                                                 │
│  4. POST-TURN WRITE (auto episodic)                             │
│     ├─ log_activity(mission, action, status)                    │
│     │   └─ memory_mcp.write_episode(                            │
│     │         agent_role=role,                                  │
│     │         mission_id=mission_id,                            │
│     │         turn_number=turn_count,                           │
│     │         text="Action: {action} | Status: {status}",       │
│     │         correlation_id=correlation_id,                    │
│     │         tenant_id=tenant_id                               │
│     │       )                                                   │
│     └─ VectorizationPipeline.ingest() → Qdrant mem_episodic    │
│                                                                 │
│  5. OPTIONAL SEMANTIC/PROCEDURAL (tool-call triggered)          │
│     ├─ If agent calls memory.search_semantic → retrieve policy  │
│     ├─ If agent calls memory.search_procedures → tool patterns │
│     └─ Results injected into next turn context                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Consequences

### Positive
- Agents gain persistent memory across missions (episodic, semantic, procedural)
- Pre-turn RAG grounds decisions in historical context without operator intervention
- Tier-based token budget prevents context overflow and cost runaway
- Explicit `tenant_id` enables multi-tenant deployments from day one
- All memory writes flow through the vectorization pipeline (chunk → embed → index)
- Operator can query past decisions via WebUI pipeline tools

### Negative
- bge-m3 requires ~4GB RAM (drives node pool sizing)
- Pre-turn RAG adds ~50-200ms latency per agent turn (acceptable for most missions)
- 1024-dim vectors consume ~33% more storage than 768-dim
- Context budget enforcement requires prompt engineering for optimal truncation

### Risks
- OLLAMA bge-m3 OOM on memory-constrained environments → mitigated by fallback to nomic-embed-text
- Relevance < 0.75 on domain-specific queries → mitigated by golden eval set and iteration
- Agent latency > 2s with RAG → mitigated by async pre-fetch and embedding cache

---

## Acceptance Criteria

### Write Path
| Criterion | Test | Threshold |
|-----------|------|-----------|
| log_activity → Qdrant latency | `pytest tests/agents/test_memory_write.py` | p99 < 500ms |
| Zero agent-block on memory failure | Kill Qdrant, run agent turn | Agent completes successfully |
| Idempotent writes | Call write_episode twice (same mission+turn) | Single chunk in Qdrant |
| Provenance captured | Inspect Qdrant payload | input_hash, pipeline_step, correlation_id present |
| tenant_id present | Inspect Qdrant payload | tenant_id field exists |

### Read Path
| Criterion | Test | Threshold |
|-----------|------|-----------|
| Pre-turn RAG latency | `pytest tests/agents/test_memory_read.py` | p99 < 200ms (cached) |
| Relevance @ top-5 | `pytest tests/eval/test_memory_relevance.py` | NDCG@5 ≥ 0.75 |
| Metadata filters work | search_episodes with role+mission | Only matching results |
| Context budget respected | Inject top-5, measure tokens | ≤ tier budget |

### Integration
| Criterion | Test | Threshold |
|-----------|------|-----------|
| MCP tool registration | mesh gateway /mcp/discover | 6 memory tools present |
| Agent uses memory before inference | Spy on llm_generate() | RAG results in context (turn 2+) |
| Collection auto-create | Fresh Qdrant + gateway start | 10 collections exist |
| bge-m3 dimension consistency | Query embed dim == Qdrant vector size | 1024 == 1024 |

---

## Implementation Phases

| Phase | Scope | Sprint | Owner |
|-------|-------|--------|-------|
| 1 | Core write path verification + tenant_id wiring | 1 | Platform |
| 2 | Pre-turn RAG injection + token budget | 1 | Backend |
| 3 | Semantic/procedural agent tools + Dictator writes | 2 | AI/ML |
| 4 | Golden eval set + relevance tuning | 2 | AI/ML |
| 5 | Load testing + operational hardening | 3 | DevOps |
| 6 | WebUI operator memory panel | 2 | Backend |

---

## Compliance

| Provision | ADR-010 | ADR-014 | DTP §2.3 | DTP §4.2 |
|-----------|---------|---------|----------|----------|
| Dual-path architecture | Extends §4 | Extends §2 | Memory layer | Agent context |
| Pre-turn RAG injection | New §5.1 | — | Agent lifecycle | — |
| Tier-based token budget | — | — | — | Model routing |
| tenant_id in payloads | New field | Extends schema | — | Multi-tenancy |
| Embedding cache 24h TTL | §4.4 update | — | — | Redis config |

---

## References

- ADR-010: Vectorized Data Mesh Architecture
- ADR-014: Mesh Gateway Memory Integration & Embedding Model Upgrade
- `magenta/mesh/memory.py` — MemoryMCPServer (6 MCP tools)
- `magenta/agents/base.py` — LLMAgent.log_activity() wired to memory MCP
- `magenta/mesh/pipeline.py` — VectorizationPipeline (chunker → embedder → indexer)
- `architecture/data-mesh/readme.md` — Full data mesh design

---

## Notes

- The mesh gateway is the single integration point for all memory operations — no separate memory service.
- Memory writes are fire-and-forget from the agent's perspective (non-blocking).
- The `embed_single` method in OllamaEmbedder handles query embedding for search.
- Collection configs are defined in both K8s ConfigMap and Python `collections.py` for consistency.
- This ADR supersedes ADR-010 §4 and ADR-014 §2 where they conflict.
