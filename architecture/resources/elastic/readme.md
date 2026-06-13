# Elasticsearch Architecture & Sizing

## Component Overview

Elasticsearch serves as Magenta's **Hot Registry** — the real-time queryable store for:

- `automation-activity` — canonical activity events (see `data/elastic/indices.py`)
- `missions` — current and recent mission state
- `agent-logs` — per-turn LLM prompts, responses, and latencies

Three index mappings defined in `magenta/data/elastic/indices.py`:

```python
# Index templates from the codebase
INDICES = {
    "automation-activity": {  # 3 shards, 1 replica, ILM: hot-warm-cold
        "mappings": { ... keyword, integer, date, object fields ... }
    },
    "missions": {             # default shard count
        "mappings": { ... keyword, text, integer, date fields ... }
    },
    "agent-logs": {           # default shard count
        "mappings": { ... keyword, text, integer fields ... }
    }
}
```

## Index Lifecycle Management (ILM)

Policy: `magenta-hot-warm-cold` (defined in config)

| Phase | Duration | Action | Nodes |
|---|---|---|---|
| Hot | 7 days | Indexing + query, 3 shards × 1 replica | Hot data nodes (SSD) |
| Warm | 30 days | Read-only, reduce to 1 replica | Warm data nodes (HDD) |
| Cold | 365 days | Searchable snapshot | Cold data nodes (HDD) |
| Delete | After 365 days | `delete` action | — |

```json
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": { "rollover": { "max_primary_shard_size": "50gb" } }
      },
      "warm": {
        "min_age": "7d",
        "actions": {
          "allocate": { "number_of_replicas": 1, "require": { "data": "warm" } },
          "forcemerge": { "max_num_segments": 1 }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "allocate": { "require": { "data": "cold" } },
          "searchable_snapshot": { "snapshot_repository": "magenta-archive" }
        }
      },
      "delete": { "min_age": "365d", "actions": { "delete": {} } }
    }
  }
}
```

## Shard Calculus

```yaml
shard_size_target: 50gb  # per primary shard
shards_per_index: 3
replicas: 1
total_shards: 6           # 3 primary + 3 replica
```

| Index | Daily Volume | Shards | Size per Shard (30 days) |
|---|---|---|---|
| automation-activity | ~20 MB | 3 | ~200 MB |
| missions | ~2 MB | 3 | ~20 MB |
| agent-logs | ~100 MB | 3 | ~1 GB |

## Cluster Topology

### Small (dev/staging)

```
3 nodes: 4 CPU, 8 GB RAM, 200 GB SSD each
Roles: master + data + ingest (all-in-one)
```

### Production

| Node Role | Count | CPU | RAM | Storage | Notes |
|---|---|---|---|---|---|
| Master | 3 | 2 CPU | 4 GB | 20 GB SSD | Dedicated, voting only |
| Hot data | 3 | 8 CPU | 16 GB | 500 GB SSD (NVMe) | Indexing + recent queries |
| Warm data | 3 | 4 CPU | 8 GB | 2 TB HDD | Read-only, force-merged |
| Cold data | 2 | 4 CPU | 8 GB | 5 TB HDD | Snapshot mounts |
| Coordinating | 2 | 8 CPU | 16 GB | — | Query routing |
| **Total** | **13** | | | | |

## Query Performance Tuning

```yaml
# elasticsearch.yml
indices.memory.index_buffer_size: 10%
indices.queries.cache.size: 10%
indices.fielddata.cache.size: 20%
search.max_buckets: 10000

# Config from codebase
MAGENTA_ELASTIC__INDEX_PREFIX: "magenta"
MAGENTA_ELASTIC__ILM_POLICY: "magenta-hot-warm-cold"
```

## TLS & Security

```yaml
elastic:
  hosts:
    - https://es-node1:9200
    - https://es-node2:9200
    - https://es-node3:9200
  username: magenta-sa
  password: ${ES_PASSWORD}
  tls:
    verify_certs: true
    ca_certs: /etc/elasticsearch/certs/ca.pem
    client_cert: /etc/elasticsearch/certs/magenta.pem
    client_key: /etc/elasticsearch/certs/magenta-key.pem
```

## Monitoring

| Metric | Alert |
|---|---|
| Cluster health != green | Critical |
| JVM heap > 85% | Warning |
| Search latency p99 > 1 s | Warning |
| Indexing rate drop > 50% | Investigate |
| Disk > 80% on any data node | Warning |
| Disk > 90% on any data node | Critical |
| Shard count per node > 1000 | Warning |
