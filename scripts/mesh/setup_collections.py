#!/usr/bin/env python3
"""Setup Qdrant collections for Magenta memory (ADR-018).

Creates the 3 memory collections with correct vector config:
- mem_episodic: 1024-dim, cosine, tenant-indexed
- mem_semantic: 1024-dim, cosine, product+tag indexed
- mem_procedural: 1024-dim, cosine, tool-name indexed

Usage:
    python scripts/mesh/setup_collections.py --env dev
    python scripts/mesh/setup_collections.py --env dev --force  # recreate
    python scripts/mesh/setup_collections.py --env dev --dry-run
"""

import argparse
import json
import sys

import httpx


COLLECTIONS = {
    "mem_episodic": {
        "vectors": {
            "size": 768,
            "distance": "Cosine",
        },
        "indexing_threshold": 20000,
        "optimizer_config": {
            "deleted_threshold": 0.2,
            "indexing_threshold": 20000,
        },
    },
    "mem_semantic": {
        "vectors": {
            "size": 768,
            "distance": "Cosine",
        },
        "indexing_threshold": 20000,
    },
    "mem_procedural": {
        "vectors": {
            "size": 768,
            "distance": "Cosine",
        },
        "indexing_threshold": 20000,
    },
}


def check_qdrant(url: str) -> bool:
    """Check Qdrant is reachable."""
    try:
        r = httpx.get(f"{url}/healthz", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


def list_collections(url: str) -> dict:
    """List existing collections."""
    try:
        r = httpx.get(f"{url}/collections", timeout=10.0)
        return {c["name"]: c for c in r.json().get("collections", [])}
    except Exception as e:
        print(f"  Error listing collections: {e}")
        return {}


def create_collection(url: str, name: str, config: dict, force: bool = False) -> bool:
    """Create a collection if it doesn't exist."""
    collections = list_collections(url)

    if name in collections and not force:
        print(f"  [{name}] Already exists, skipping")
        return True

    if name in collections and force:
        print(f"  [{name}] Deleting existing collection...")
        try:
            r = httpx.delete(f"{url}/collections/{name}", timeout=10.0)
            if r.status_code != 200:
                print(f"  [{name}] Delete failed: {r.status_code}")
                return False
        except Exception as e:
            print(f"  [{name}] Delete error: {e}")
            return False

    # Create collection
    try:
        payload = {
            "vectors": config["vectors"],
        }
        r = httpx.put(
            f"{url}/collections/{name}",
            json=payload,
            timeout=30.0,
        )
        if r.status_code == 200:
            print(f"  [{name}] Created successfully")
            return True
        else:
            print(f"  [{name}] Create failed: {r.status_code} {r.text[:200]}")
            return False
    except Exception as e:
        print(f"  [{name}] Create error: {e}")
        return False


def create_payload_index(url: str, collection: str, field: str, schema: str) -> bool:
    """Create a payload index for metadata filtering."""
    try:
        payload = {
            "field_name": field,
            "field_schema": schema,
        }
        r = httpx.put(
            f"{url}/collections/{collection}/index",
            json=payload,
            timeout=10.0,
        )
        if r.status_code == 200:
            print(f"  [{collection}] Indexed field: {field} ({schema})")
            return True
        else:
            # Index may already exist
            print(f"  [{collection}] Index {field}: {r.status_code}")
            return True
    except Exception as e:
        print(f"  [{collection}] Index error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Setup Qdrant collections")
    parser.add_argument("--env", default="dev")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--force", action="store_true", help="Recreate collections")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--indexes", action="store_true", help="Create payload indexes")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Qdrant Collections Setup — {args.env.upper()}")
    print(f"{'='*60}\n")

    # Check Qdrant
    if not args.dry_run and not check_qdrant(args.qdrant_url):
        print(f"  ERROR: Qdrant not reachable at {args.qdrant_url}")
        sys.exit(1)

    # Create collections
    success = 0
    for name, config in COLLECTIONS.items():
        if args.dry_run:
            print(f"  [{name}] Would create with dim={config['vectors']['size']}")
            success += 1
        else:
            if create_collection(args.qdrant_url, name, config, force=args.force):
                success += 1

    # Create payload indexes
    if args.indexes and not args.dry_run:
        print("\nCreating payload indexes...")
        indexes = [
            ("mem_episodic", "agent_role", "keyword"),
            ("mem_episodic", "mission_id", "keyword"),
            ("mem_episodic", "tenant_id", "keyword"),
            ("mem_episodic", "memory_type", "keyword"),
            ("mem_episodic", "created_at", "integer"),
            ("mem_semantic", "product", "keyword"),
            ("mem_semantic", "tags", "keyword"),
            ("mem_procedural", "tool_name", "keyword"),
            ("mem_procedural", "tenant_id", "keyword"),
        ]
        for collection, field, schema in indexes:
            create_payload_index(args.qdrant_url, collection, field, schema)

    print(f"\n{'='*60}")
    print(f"  Result: {success}/{len(COLLECTIONS)} collections ready")
    print(f"{'='*60}\n")

    sys.exit(0 if success == len(COLLECTIONS) else 1)


if __name__ == "__main__":
    main()
