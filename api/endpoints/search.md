# Search API

## `GET /api/v1/search`

Cross-registry search across Elasticsearch hot index, Sentinel custom tables, and Data Lake cold storage.

| Query Param | Type | Default | Description |
|---|---|---|---|
| `q` | string | — | Search query |
| `source` | string | `all` | Filter: `elastic`, `sentinel`, `lake` |
| `limit` | int | 50 | Max results |

```json
{
  "query": "ransomware",
  "source": "all",
  "total": 42,
  "results": [...],
  "took_ms": 185
}
```

> **Note**: Current implementation is a stub (`magenta/api/routes/search.py`). Real implementation queries Elasticsearch, Sentinel Log Analytics, and Data Lake in parallel.

## `GET /api/v1/search/activity`

Search `automation.activity` events with structured filters.

| Query Param | Type | Default | Description |
|---|---|---|---|
| `correlation_id` | UUID | — | Filter by correlation |
| `alert_id` | string | — | Filter by source alert |
| `action` | string | — | Filter by action type |
| `status` | string | — | Filter by action status |
| `limit` | int | 50 | Max results |

```json
{
  "filters": {
    "correlation_id": "550e8400-...",
    "alert_id": "sentinel-incident-8932",
    "action": "isolate_host",
    "status": "succeeded"
  },
  "total": 1,
  "results": [
    {
      "event_id": "uuid",
      "action": "isolate_host",
      "status": "succeeded",
      "target": {"type": "host", "id": "FIN-PROD-347"},
      "started_at": "2026-06-13T14:05:00Z"
    }
  ]
}
```
