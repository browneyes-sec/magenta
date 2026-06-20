#!/usr/bin/env python3
"""Retention TTL Cleanup Job — deletes expired points from Qdrant collections.

Removes points older than configured TTL per memory type.
Run as cron job or K8s CronJob.

Usage:
    python scripts/mesh/retention_cleanup.py --env dev --dry-run
    python scripts/mesh/retention_cleanup.py --env dev
"""

import argparse
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from magenta.mesh.config import MeshConfig
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, DatetimeRange


# Retention policies per memory type (in days)
RETENTION_DAYS = {
    "mem_episodic": 90,   # Hot: 90 days, then archive
    "mem_semantic": 365,  # Warm: 1 year
    "mem_procedural": 730, # Warm: 2 years
}


def get_qdrant_client(config: MeshConfig) -> QdrantClient:
    return QdrantClient(
        host=config.qdrant.host,
        port=config.qdrant.port,
        prefer_grpc=config.qdrant.use_grpc,
    )


def cleanup_collection(client: QdrantClient, collection: str, days: int, dry_run: bool = False) -> int:
    """Delete points older than `days` from collection.

    Uses the `timestamp` field in payload for age calculation.
    """
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    # Build filter for points older than cutoff
    flt = Filter(
        must=[
            FieldCondition(
                key="timestamp",
                range=DatetimeRange(lt=cutoff_iso),
            )
        ]
    )

    # Count points to delete
    count_result = client.count(
        collection_name=collection,
        count_filter=flt,
        exact=True,
    )
    to_delete = count_result.count

    if to_delete == 0:
        print(f"  {collection}: No expired points (retention: {days}d)")
        return 0

    if dry_run:
        print(f"  [DRY-RUN] {collection}: Would delete {to_delete} points older than {days}d (cutoff: {cutoff_iso})")
        return 0

    # Delete in batches
    deleted = 0
    batch_size = 1000

    while deleted < to_delete:
        # Scroll to get points to delete
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=flt,
            limit=batch_size,
            with_payload=False,
            with_vectors=False,
        )

        if not points:
            break

        point_ids = [str(p.id) for p in points]
        client.delete(collection_name=collection, points_selector=point_ids)
        deleted += len(point_ids)

        if deleted % 1000 == 0:
            print(f"  {collection}: Deleted {deleted}/{to_delete}...")

    print(f"  {collection}: Deleted {deleted} points older than {days}d")
    return deleted


def main():
    parser = argparse.ArgumentParser(description="Qdrant Retention Cleanup")
    parser.add_argument("--env", default="dev", choices=["dev", "staging", "prod"])
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    parser.add_argument("--collection", help="Specific collection to clean (default: all)")
    args = parser.parse_args()

    # Load config
    config = MeshConfig.from_env()
    if args.env == "staging":
        config.qdrant.host = "qdrant"
    elif args.env == "prod":
        config.qdrant.host = "qdrant"

    client = get_qdrant_client(config)

    print(f"Retention Cleanup — {args.env}")
    print("=" * 50)

    if args.dry_run:
        print("DRY RUN MODE — no deletions will occur")
        print()

    collections = [args.collection] if args.collection else list(RETENTION_DAYS.keys())

    total_deleted = 0
    for collection in collections:
        if collection not in RETENTION_DAYS:
            print(f"  {collection}: Unknown collection, skipping")
            continue

        days = RETENTION_DAYS[collection]
        deleted = cleanup_collection(client, collection, days, dry_run=args.dry_run)
        total_deleted += deleted

    print("=" * 50)
    if args.dry_run:
        print(f"DRY RUN complete. Total would delete: {total_deleted}")
    else:
        print(f"Cleanup complete. Total deleted: {total_deleted}")


if __name__ == "__main__":
    main()