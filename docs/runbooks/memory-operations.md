# Memory Operations Runbook

Operational procedures for monitoring, validating, and maintaining the agent memory infrastructure.

## Quick Health Check

```bash
# Full validation (dev)
python scripts/mesh/validate_memory.py --env dev --verbose

# JSON output for CI/monitoring
python scripts/mesh/validate_memory.py --env dev --output json

# With write/read round-trip test
python scripts/mesh/validate_memory.py --env dev --write-test
```

## RAG Accuracy Measurement

```bash
# Run full eval against golden dataset
python scripts/mesh/rag_accuracy.py --env dev --verbose

# NDCG@5 only (quick check)
python scripts/mesh/rag_accuracy.py --env dev --ndcg-only

# Custom golden file
python scripts/mesh/rag_accuracy.py --env dev --golden tests/eval/memory_golden.jsonl --verbose
```

## Collection Management

### Check Vector Counts

```bash
curl -s http://localhost:6333/collections | jq '.collections[] | {name, points: .points_count}'
```

### Manual Point Inspection

```bash
# Sample 5 points from episodic memory
curl -s -X POST http://localhost:6333/collections/episodic_memory/points/scroll \
  -H 'Content-Type: application/json' \
  -d '{"limit": 5, "with_payload": true}' | jq '.result.points[].payload'
```

### Delete Expired Points (Retention Enforcement)

```bash
# Dry run: count points older than 90 days
CUTOFF_MS=$(($(date +%s) - 90 * 86400))000
curl -s -X POST http://localhost:6333/collections/episodic_memory/points/scroll \
  -H 'Content-Type: application/json' \
  -d "{\"limit\": 1000, \"filter\": {\"must\": [{\"key\": \"created_at\", \"range\": {\"lt\": $CUTOFF_MS}}]}}" | jq '.result.points | length'

# Actually delete (use with caution)
curl -X POST http://localhost:6333/collections/episodic_memory/points/delete \
  -H 'Content-Type: application/json' \
  -d "{\"filter\": {\"must\": [{\"key\": \"created_at\", \"range\": {\"lt\": $CUTOFF_MS}}]}}"
```

## Embedding Cache Monitoring

```bash
# Check Redis cache stats
redis-cli INFO keyspace
redis-cli GET "embed_cache:hits"
redis-cli GET "embed_cache:misses"

# Check cache size
redis-cli DBSIZE

# Flush cache (if needed)
redis-cli FLUSHDB
```

## Troubleshooting

### "Qdrant unreachable"

1. Check container status: `docker ps | grep qdrant`
2. Check logs: `docker logs magenta-qdrant --tail 50`
3. Check port: `curl http://localhost:6333/healthz`
4. Restart: `docker restart magenta-qdrant`

### "Embedding model not found"

1. Check OLLAMA models: `curl http://localhost:11434/api/tags`
2. Pull bge-m3: `docker exec magenta-ollama ollama pull bge-m3`
3. Verify dimension: run a test embed and check vector length is 1024

### "NDCG@5 below target (0.75)"

1. Run with `--verbose` to identify failing queries
2. Check if relevant points exist in the collection
3. Verify embedding model is bge-m3 (not a smaller model)
4. Check for stale embeddings (re-index if model was updated)
5. Review golden dataset for relevance labeling errors

### "Write latency > 200ms"

1. Check Qdrant disk I/O: `docker exec magenta-qdrant iostat -x 1 5`
2. Check vector count: large collections slow down writes
3. Consider sharding: split by tenant_id or time range
4. Check embedding latency separately (OLLAMA cold start?)

### "Token budget exceeded"

1. Check `token_count` in eval results
2. Review max_tokens configuration per tier
3. Implement aggressive truncation for cost_save tier
4. Consider increasing `recall@5` threshold to reduce context length

## Monitoring Integration

### Prometheus Metrics (Planned)

```yaml
# Add to prometheus.yml
- job_name: 'magenta-memory'
  static_configs:
    - targets: ['qdrant:6333']
  metrics_path: /metrics
```

### Grafana Dashboard Queries

```promql
# Vector count per collection
qdrant_collection_points_total

# Search latency p99
histogram_quantile(0.99, rate(qdrant_search_duration_seconds_bucket[5m]))

# Embedding cache hit rate
redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)
```

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Qdrant health | not green | unreachable |
| NDCG@5 | < 0.75 | < 0.50 |
| Search latency p95 | > 300ms | > 1000ms |
| Embedding latency | > 500ms | > 2000ms |
| Cache hit rate | < 80% | < 50% |
| Points per collection | > 10M | > 50M |
| Expired points | > 1000 | > 10000 |

## Backup & Recovery

See [qdrant-backup.md](qdrant-backup.md) for:
- Snapshot creation and restoration
- Cross-environment migration
- Point-level export/import

## CI/CD Integration

The `architecture-compliance.yml` workflow runs:
- `test_memory_write.py` — unit tests for write path
- `test_memory_read.py` — unit tests for read path
- Schema validation — verifies memory tool signatures

To add RAG accuracy gates to CI:

```yaml
  rag-accuracy-gate:
    name: RAG Accuracy Gate
    runs-on: ubuntu-latest
    services:
      qdrant:
        image: qdrant/qdrant:latest
        ports: ["6333:6333"]
      ollama:
        image: ollama/ollama:latest
        ports: ["11434:11434"]
    steps:
      - uses: actions/checkout@v4
      - name: Pull embedding model
        run: docker exec ollama ollama pull bge-m3
      - name: Seed test data
        run: python scripts/mesh/seed_eval_data.py
      - name: Run accuracy eval
        run: python scripts/mesh/rag_accuracy.py --env dev
```
