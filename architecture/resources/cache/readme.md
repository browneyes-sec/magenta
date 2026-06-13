# Cache Architecture & Sizing

## Component Overview

Magenta uses caching at three layers:

1. **Mission State** (Redis) — active mission contexts, agent task assignments, approval queue
2. **LLM Response Cache** — deduplicate repeated model queries (same prompt + context)
3. **Idempotency Store** — prevent duplicate action execution within retention window

## Redis — Mission State Store

Primary cache for runtime state. The `orchestration/state.py` module implements an in-memory store with Redis as the production backend.

### Data Stored

| Key Pattern | TTL | Size per Key |
|---|---|---|
| `mission:{id}:state` | Mission TTL + 1h | ~2 KB |
| `mission:{id}:tasks` | Mission TTL | ~1 KB per task |
| `mission:{id}:artifacts` | Mission TTL + 24h | Variable (up to 1 MB) |
| `agent:{id}:context` | 30 min | ~50 KB per turn |
| `approval:{correlation_id}` | 15 min | ~1 KB |
| `idempotency:{key}` | 24 h | ~200 B |

### Sizing

| Active Missions | Redis Memory |
|---|---|
| 10 | 128 MB |
| 100 | 512 MB |
| 500 | 2 GB |
| 1000 | 4 GB |

### Eviction Policy

```conf
maxmemory-policy allkeys-lru
```

Persistence: RDB snapshots every 5 min (AOF optional, acceptable data loss is mission replay).

## LLM Response Cache

### Strategy

- **Cache key**: `sha256(prompt + system_instructions + model_name + temperature)`
- **Scope**: Per model, per agent role
- **TTL**: 1 hour (tunable)
- **Invalidation**: On model version change or agent instruction update

### Effectiveness

| Agent Role | Cache Hit Rate (est.) | Rationale |
|---|---|---|
| Triage (severity classification) | 60-70% | Repetitive alert patterns |
| Enrich (context lookup) | 30-40% | Diverse queries |
| Contain (action selection) | 50-60% | Common action patterns |
| Investigation | < 10% | Unique per incident |
| Compliance | 80-90% | Template-driven reports |

```python
# magenta/models/cache.py (conceptual)
class LLMResponseCache:
    def __init__(self, redis_client, ttl: int = 3600):
        self._redis = redis_client
        self._ttl = ttl

    async def get(self, key: str) -> Optional[str]:
        return await self._redis.get(f"llm-cache:{key}")

    async def set(self, key: str, response: str) -> None:
        await self._redis.setex(f"llm-cache:{key}", self._ttl, response)
```

## Idempotency Store

Every `AutomationActivity` carries an `idempotency_key` derived from `source_alert_id + action + target.id`. Before executing any action, Magenta checks this key against the cache.

```yaml
idempotency:
  backend: redis
  ttl_hours: 24
  key_prefix: "idempotency"
```

## Configuration

```yaml
# config/default.yaml — cache-related settings
cache:
  backend: redis
  host: localhost
  port: 6379
  db: 0
  mission_ttl_seconds: 86400
  llm_cache_ttl: 3600
  idempotency_ttl: 86400
```

## Monitoring

| Metric | Alert |
|---|---|
| Redis memory > 80% maxmemory | Warning |
| Redis hit rate < 50% (LLM cache) | Info |
| Idempotency collision rate > 0.1% | Warning |
| Redis latency p99 > 10 ms | Warning |
| Eviction rate > 100 keys/min | Critical — increase memory |
