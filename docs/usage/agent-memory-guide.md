# Agent Memory Guide — Magenta ASOAR

**Version:** 1.0  
**Classification:** Internal Operations Guide  
**Ref:** ADR-018 (LLM-RAG Hybrid Memory Architecture)

---

## 1. What Is Agent Memory?

Agent memory is Magenta's mechanism for persisting and retrieving contextual information across missions. Every agent action, decision, and outcome is written to the vectorized data mesh (Qdrant) and can be retrieved for future context.

Memory enables agents to:
- Recall past decisions in similar incidents
- Learn tool usage patterns from previous missions
- Apply established playbooks and runbooks
- Avoid repeating mistakes

---

## 2. Memory Types

| Type | What It Stores | Collection | When Written | When Read |
|------|---------------|------------|--------------|-----------|
| **Episodic** | Mission transcripts, agent decisions, actions | `mem_episodic` | Auto (every turn, post-action) | Auto (pre-turn, turn 2+) |
| **Semantic** | Playbooks, runbooks, policies, knowledge base | `mem_semantic` | On-demand (Dictator directives, operator uploads) | On-demand (agent tool call) |
| **Procedural** | Tool invocation patterns, parameter combinations | `mem_procedural` | Auto (after each tool execution) | On-demand (agent tool call) |

---

## 3. How Memory Works

### 3.1 Write Path (Automatic)

Every agent turn follows this write path:

```
Agent executes action
    │
    ▼
log_activity(mission, action, status)
    │
    ▼
memory_mcp.write_episode()
    │
    ▼
VectorizationPipeline.ingest()
    ├─► SemanticChunker (512 tokens, 64 overlap)
    ├─► OllamaEmbedder.embed() [bge-m3, 1024-dim]
    └─► QdrantIndexer.upsert(collection="mem_episodic")
```

**What gets written:**
```json
{
  "id": "M123:triage:t3",
  "text": "Action: disable_account | Status: success | Alert: sentinel-8932",
  "metadata": {
    "agent_role": "triage",
    "mission_id": "M123",
    "turn_number": 3,
    "correlation_id": "abc-123",
    "tenant_id": "acme-corp",
    "memory_type": "episodic",
    "provenance": {
      "pipeline_step": "memory.write_episode",
      "input_hash": "a1b2c3d4..."
    }
  }
}
```

### 3.2 Read Path (Pre-Turn RAG)

Before every agent turn (turn 2+), the system automatically retrieves relevant past decisions:

```
Agent receives new alert
    │
    ▼
retrieve_context(alert_summary)
    │
    ▼
memory_mcp.search_episodes(
    query=alert_summary,
    agent_role="triage",
    mission_id="M456",
    tenant_id="acme-corp",
    top_k=3
)
    │
    ▼
Truncate to tier budget (speed=1000, reasoning=3000, cost=500 tokens)
    │
    ▼
Inject into system_prompt as "Relevant Past Decisions"
```

### 3.3 On-Demand Read (Agent Tool Calls)

Agents can explicitly search memory using MCP tools:

| Tool | Use Case | Example |
|------|----------|---------|
| `memory.search_semantic` | Find relevant playbook | "What's the ransomware containment procedure?" |
| `memory.search_procedures` | Find tool usage pattern | "How was entra_disable_account used before?" |
| `memory.search_episodes` | Find past similar incidents | "What happened in the last phishing mission?" |

---

## 4. Operator Commands (Open WebUI)

### 4.1 Via Dictator Pipeline

| Command | What It Does |
|---------|--------------|
| `dictator_status` | Shows framework state, agent count, policies |
| `registry_search` | Lists all missions from registry |
| `check_pending_approvals` | Lists actions waiting for human approval |
| `policy_list` | Lists active policies and overrides |
| `connector_health` | Shows connector/service health |

### 4.2 Via Artifacts Pipeline

| Command | What It Does |
|---------|--------------|
| `generate_artifact mission_throughput` | Mission throughput chart |
| `generate_artifact threat_analytics` | Threat analytics dashboard |
| `generate_artifact policy_status` | Policy status dashboard |
| `generate_artifact directive_timeline` | Directive timeline dashboard |
| `generate_artifact dead_letter` | Dead letter queue dashboard |
| `generate_artifact blue_team_ops` | Blue team operations dashboard |

---

## 5. Configuration

### 5.1 Memory Flags (agents.toml)

```toml
[agent.memory]
enabled = true
pre_turn_rag = true
episodic_injection = "auto"      # auto | manual | disabled
semantic_injection = "tool"      # tool | auto | disabled
procedural_injection = "tool"    # tool | auto | disabled

[agent.memory.budget]
speed = 1000          # tokens for speed tier
reasoning = 3000      # tokens for reasoning tier
cost_save = 500       # tokens for cost_save tier

[agent.memory.tenant]
default_id = "default"
```

### 5.2 Embedding Cache (Redis)

```bash
# Check cache stats
redis-cli INFO stats | grep keyspace

# Check cache hit rate
redis-cli INFO stats | grep keyspace_hits

# Clear cache (if needed)
redis-cli FLUSHDB
```

---

## 6. Operational Validation

### 6.1 Memory Infrastructure Health Check

Run the validation script to verify all memory components:

```bash
# Full validation (dev)
python scripts/mesh/validate_memory.py --env dev --verbose

# With write/read round-trip test
python scripts/mesh/validate_memory.py --env dev --write-test

# JSON output for CI/monitoring
python scripts/mesh/validate_memory.py --env dev --output json
```

**Checks performed:**
- Qdrant connection health
- Collection existence and vector counts
- Embedding model availability (bge-m3)
- Write → Read round-trip latency
- Schema compliance (required fields present)
- Retention policy enforcement

### 6.2 RAG Accuracy Measurement

Measure retrieval quality against a golden dataset:

```bash
# Seed eval data
python scripts/mesh/seed_eval_data.py --env dev --clear-first

# Run accuracy eval
python scripts/mesh/rag_accuracy.py --env dev --verbose

# NDCG@5 only (quick check)
python scripts/mesh/rag_accuracy.py --env dev --ndcg-only
```

**Metrics tracked:**
- **NDCG@5**: Normalized Discounted Cumulative Gain (target: ≥ 0.75)
- **Precision@1**: Top result relevance
- **Recall@5**: Relevant items found in top 5
- **Latency**: End-to-end query → context time

### 6.3 Golden Dataset

The eval dataset lives at `tests/eval/memory_golden.jsonl`:

```json
{
  "query": "Ransomware encrypting file shares on FIN-PROD-347",
  "relevant_ids": ["ep-20260601-001", "ep-20260610-014"],
  "irrelevant_ids": ["ep-20260501-003"],
  "tier": "episodic",
  "expected_answer": "Prior ransomware activity on same host 3 days ago"
}
```

To add new test cases:
1. Add a JSONL line with `query`, `relevant_ids`, `tier`, `expected_answer`
2. Run `seed_eval_data.py --clear-first` to refresh test vectors
3. Run `rag_accuracy.py` to verify NDCG@5 ≥ 0.75

### 6.4 Alert Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Qdrant health | not green | unreachable | Restart container |
| NDCG@5 | < 0.75 | < 0.50 | Review embedding model, re-index |
| Search latency p95 | > 300ms | > 1000ms | Check disk I/O, shard collection |
| Embedding latency | > 500ms | > 2000ms | Check OLLAMA, pull model |
| Cache hit rate | < 80% | < 50% | Increase Redis memory |
| Points per collection | > 10M | > 50M | Archive old points |

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent not retrieving past decisions | pre_turn_rag disabled | Set `agent.memory.pre_turn_rag = true` in agents.toml |
| Slow agent turns (> 2s) | RAG cold query | Check OLLAMA health; increase Redis cache TTL |
| Memory not persisting | Qdrant connection failed | Check `docker logs magenta-api` for mesh errors |
| Wrong tenant data visible | tenant_id mismatch | Verify all payloads have correct tenant_id |
| Embedding dimension mismatch | bge-m3 not loaded | `docker exec magenta-ollama ollama pull bge-m3` |
| NDCG@5 below target | Stale embeddings | Re-seed eval data, verify bge-m3 model |
| Write latency > 200ms | Disk I/O bottleneck | Check Qdrant disk usage, consider sharding |

---

## 8. Monitoring

### 7.1 Key Metrics

| Metric | Threshold | Alert |
|--------|-----------|-------|
| Memory write latency (p99) | < 500ms | Critical if > 1s |
| Memory read latency (p99) | < 200ms (cached) | Warning if > 500ms |
| Embedding cache hit rate | > 80% | Warning if < 60% |
| Qdrant collection size | < 10GB | Critical if > 50GB |
| Agent memory failure rate | < 1% | Critical if > 5% |

### 7.2 Health Checks

```bash
# Check mesh gateway health
curl http://localhost:8000/api/v1/mesh/health

# Check Qdrant collections
curl http://localhost:6333/collections

# Check OLLAMA embedding model
curl http://localhost:11434/api/tags
```

---

## 8. Backup & Restore

See [qdrant-backup.md](../runbooks/qdrant-backup.md) for procedures.

---

## 9. References

- ADR-010: Vectorized Data Mesh Architecture
- ADR-014: Mesh Gateway Memory Integration
- ADR-018: LLM-RAG Hybrid Memory Architecture
- `magenta/mesh/memory.py` — MemoryMCPServer implementation
- `magenta/agents/base.py` — LLMAgent.log_activity() wiring
- `magenta/mesh/pipeline.py` — VectorizationPipeline
- `architecture/data-mesh/readme.md` — Full data mesh design
