#!/usr/bin/env python3
"""Qdrant Backup Automation — snapshot and restore.

Creates snapshots of all Qdrant collections for backup purposes.
Snapshots are stored in Qdrant's snapshot directory.

Usage:
    python scripts/mesh/qdrant_backup.py --env dev --action backup
    python scripts/mesh/qdrant_backup.py --env dev --action list
    python scripts/mesh/qdrant_backup.py --env dev --action restore --snapshot <name>
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def get_qdrant_url(env: str) -> str:
    """Get Qdrant URL based on environment."""
    urls = {
        "dev": "http://localhost:6333",
        "staging": "http://qdrant:6333",
        "prod": "http://qdrant:6333",
    }
    return urls.get(env, urls["dev"])


def list_snapshots(base_url: str) -> list[dict]:
    """List all snapshots across collections."""
    import httpx

    snapshots = []
    try:
        resp = httpx.get(f"{base_url}/collections")
        resp.raise_for_status()
        collections = resp.json().get("result", {}).get("collections", [])

        for col in collections:
            name = col.get("name", "")
            resp = httpx.get(f"{base_url}/collections/{name}/snapshots")
            resp.raise_for_status()
            for snap in resp.json().get("result", []):
                snapshots.append({
                    "collection": name,
                    "name": snap.get("name", ""),
                    "size": snap.get("size", 0),
                    "created_at": snap.get("created_at", ""),
                })
    except Exception as e:
        print(f"Error listing snapshots: {e}")

    return snapshots


def create_snapshots(base_url: str) -> list[dict]:
    """Create snapshots for all collections."""
    import httpx

    results = []
    try:
        resp = httpx.get(f"{base_url}/collections")
        resp.raise_for_status()
        collections = resp.json().get("result", {}).get("collections", [])

        for col in collections:
            name = col.get("name", "")
            print(f"  Creating snapshot for {name}...")
            resp = httpx.post(f"{base_url}/collections/{name}/snapshots")
            resp.raise_for_status()
            snap = resp.json().get("result", {})
            results.append({
                "collection": name,
                "snapshot": snap.get("name", ""),
                "status": "created",
            })
            print(f"    ✓ {snap.get('name', 'unknown')}")

    except Exception as e:
        print(f"Error creating snapshots: {e}")

    return results


def restore_snapshot(base_url: str, collection: str, snapshot_name: str) -> bool:
    """Restore a snapshot for a specific collection."""
    import httpx

    try:
        resp = httpx.post(
            f"{base_url}/collections/{collection}/snapshots/restore",
            json={"snapshot": snapshot_name},
        )
        resp.raise_for_status()
        print(f"  ✓ Restored {snapshot_name} for {collection}")
        return True
    except Exception as e:
        print(f"  ✗ Restore failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Qdrant Backup Automation")
    parser.add_argument("--env", default="dev", choices=["dev", "staging", "prod"])
    parser.add_argument("--action", default="backup", choices=["backup", "list", "restore"])
    parser.add_argument("--snapshot", help="Snapshot name for restore")
    parser.add_argument("--collection", help="Collection name for restore")
    args = parser.parse_args()

    base_url = get_qdrant_url(args.env)
    print(f"Qdrant Backup — {args.env} ({base_url})")
    print("=" * 50)

    if args.action == "backup":
        print("\nCreating snapshots...")
        results = create_snapshots(base_url)
        print(f"\n✓ Created {len(results)} snapshots")

    elif args.action == "list":
        print("\nExisting snapshots:")
        snapshots = list_snapshots(base_url)
        if not snapshots:
            print("  No snapshots found")
        for snap in snapshots:
            size_mb = snap["size"] / (1024 * 1024)
            print(f"  {snap['collection']}/{snap['name']} ({size_mb:.1f} MB)")

    elif args.action == "restore":
        if not args.snapshot:
            print("Error: --snapshot required for restore")
            sys.exit(1)
        if not args.collection:
            print("Error: --collection required for restore")
            sys.exit(1)
        success = restore_snapshot(base_url, args.collection, args.snapshot)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
