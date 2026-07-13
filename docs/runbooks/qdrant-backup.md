# Qdrant Backup & Restore Runbook

**Version:** 1.0  
**Classification:** Internal Operations  
**Ref:** ADR-018, ADR-010

---

## 1. Overview

This runbook covers backup and restore procedures for the Qdrant vector database used by the Magenta data mesh. Qdrant stores all agent memory vectors (episodic, semantic, procedural) and domain data products.

---

## 2. Backup Procedures

### 2.1 Snapshot Backup (Recommended)

```bash
# Create snapshot of all collections
curl -X POST "http://localhost:6333/collections/mem_episodic/snapshots" \
  -H "Content-Type: application/json" | python3 -m json.tool

curl -X POST "http://localhost:6333/collections/mem_semantic/snapshots" \
  -H "Content-Type: application/json" | python3 -m json.tool

curl -X POST "http://localhost:6333/collections/mem_procedural/snapshots" \
  -H "Content-Type: application/json" | python3 -m json.tool

# List all snapshots
curl "http://localhost:6333/collections/mem_episodic/snapshots" | python3 -m json.tool
```

### 2.2 Full Backup Script

```bash
#!/bin/bash
# qdrant-backup.sh — Full backup of all Qdrant collections
set -euo pipefail

QDRANT_URL="http://localhost:6333"
BACKUP_DIR="/opt/magenta/backups/qdrant/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

COLLECTIONS=("mem_episodic" "mem_semantic" "mem_procedural" "siem_alerts" "threat_iocs" "identity_dir")

for col in "${COLLECTIONS[@]}"; do
  echo "Backing up: $col"
  curl -X POST "$QDRANT_URL/collections/$col/snapshots" \
    -H "Content-Type: application/json" > "$BACKUP_DIR/${col}_snapshot.json"
done

echo "Backup complete: $BACKUP_DIR"
ls -la "$BACKUP_DIR"
```

### 2.3 Backup Schedule

| Collection | Frequency | Retention | Storage |
|------------|-----------|-----------|---------|
| `mem_episodic` | Daily | 30 days | Azure Blob / S3 |
| `mem_semantic` | Weekly | 90 days | Azure Blob / S3 |
| `mem_procedural` | Weekly | 30 days | Azure Blob / S3 |
| Domain collections | Daily | 30 days | Azure Blob / S3 |

---

## 3. Restore Procedures

### 3.1 Restore from Snapshot

```bash
# Restore a specific collection
curl -X PUT "http://localhost:6333/collections/mem_episodic/snapshots/restore" \
  -H "Content-Type: application/json" \
  -d '{"snapshot_url": "file:///path/to/snapshot.snapshot"}'
```

### 3.2 Full Restore Script

```bash
#!/bin/bash
# qdrant-restore.sh — Full restore from backup directory
set -euo pipefail

QDRANT_URL="http://localhost:6333"
BACKUP_DIR="$1"

if [ -z "$BACKUP_DIR" ]; then
  echo "Usage: $0 <backup-directory>"
  exit 1
fi

for snapshot_file in "$BACKUP_DIR"/*_snapshot.json; do
  col=$(basename "$snapshot_file" _snapshot.json)
  echo "Restoring: $col"
  curl -X PUT "$QDRANT_URL/collections/$col/snapshots/restore" \
    -H "Content-Type: application/json" \
    -d "{\"snapshot_url\": \"file://$snapshot_file\"}"
done

echo "Restore complete"
```

---

## 4. Migration: Re-index on Model Upgrade

When upgrading the embedding model (e.g., nomic-embed-text → bge-m3), all vectors must be re-indexed.

### 4.1 Re-index Script

```python
#!/usr/bin/env python3
"""reindex.py — Re-embed all vectors after model upgrade."""

import asyncio
import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

OLLAMA_URL = "http://localhost:11434"
QDRANT_URL = "localhost"
QDRANT_PORT = 6333
NEW_MODEL = "bge-m3"
BATCH_SIZE = 100

async def reindex_collection(collection: str):
    client = QdrantClient(host=QDRANT_URL, port=QDRANT_PORT)
    
    # Get all points
    points = client.scroll(collection_name=collection, limit=10000)[0]
    print(f"Re-indexing {len(points)} points in {collection}")
    
    async with httpx.AsyncClient(timeout=60.0) as http:
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i:i+BATCH_SIZE]
            texts = [p.payload.get("text", "") for p in batch]
            
            # Embed with new model
            resp = await http.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": NEW_MODEL, "input": texts}
            )
            new_vectors = resp.json()["embeddings"]
            
            # Upsert with new vectors
            new_points = [
                PointStruct(
                    id=batch[j].id,
                    vector=new_vectors[j],
                    payload=batch[j].payload
                )
                for j in range(len(batch))
            ]
            client.upsert(collection_name=collection, points=new_points)
            print(f"  Batch {i//BATCH_SIZE + 1}: {len(batch)} points re-indexed")

if __name__ == "__main__":
    collections = ["mem_episodic", "mem_semantic", "mem_procedural"]
    for col in collections:
        asyncio.run(reindex_collection(col))
    print("Re-index complete")
```

### 4.2 Migration Steps

1. Pull new model: `docker exec magenta-ollama ollama pull bge-m3`
2. Update config: `MESH__OLLAMA_MODEL=bge-m3`, `MESH__EMBEDDING_DIMENSION=1024`
3. Run re-index: `python scripts/mesh/reindex.py`
4. Verify: `curl http://localhost:8000/api/v1/mesh/health`
5. Restart gateway: `docker restart magenta-api`

---

## 5. Verification

### 5.1 Post-Backup Verification

```bash
# List snapshots
curl "http://localhost:6333/collections/mem_episodic/snapshots" | python3 -m json.tool

# Verify collection counts
curl "http://localhost:6333/collections/mem_episodic" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Points: {d[\"result\"][\"points_count\"]}')
print(f'Segments: {d[\"result\"][\"segments_count\"]}')
"
```

### 5.2 Post-Restore Verification

```bash
# Test search works
curl -X POST "http://localhost:8000/api/v1/mesh/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "products": ["agent.memory.episodic"], "top_k": 3}'
```

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Snapshot creation fails | Disk space | Check `df -h`; clean old snapshots |
| Restore fails with timeout | Large collection | Increase timeout; restore in batches |
| Re-index OOM | Insufficient RAM | Increase OLLAMA memory limit; process in smaller batches |
| Vector count mismatch after restore | Partial restore | Re-run restore; verify network connectivity |

---

## 7. References

- Qdrant Docs: https://qdrant.tech/documentation/
- ADR-010: Vectorized Data Mesh Architecture
- ADR-018: LLM-RAG Hybrid Memory Architecture
- `magenta/mesh/collections.py` — Collection management
- `magenta/mesh/pipeline.py` — Vectorization pipeline
