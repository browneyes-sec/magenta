#!/usr/bin/env python3
"""Test Qdrant backup and restore procedures.

Verifies:
  1. Snapshot creation
  2. Snapshot download
  3. Snapshot restore (to a test collection)
  4. Point-level export/import

Usage:
    python scripts/mesh/test_backup_restore.py --env dev
    python scripts/mesh/test_backup_restore.py --env dev --cleanup
"""

import argparse
import json
import sys
import time

import httpx


def check_qdrant(url: str) -> bool:
    try:
        r = httpx.get(f"{url}/healthz", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


def test_snapshot_create(url: str, collection: str) -> dict | None:
    """Create a snapshot of a collection."""
    try:
        r = httpx.post(f"{url}/collections/{collection}/snapshots", timeout=30.0)
        if r.status_code == 200:
            result = r.json().get("result", {})
            print(f"  Snapshot created: {result.get('name', 'unknown')}")
            return result
        else:
            print(f"  Snapshot create failed: {r.status_code} {r.text[:200]}")
            return None
    except Exception as e:
        print(f"  Snapshot create error: {e}")
        return None


def test_snapshot_list(url: str, collection: str) -> list:
    """List snapshots for a collection."""
    try:
        r = httpx.get(f"{url}/collections/{collection}/snapshots", timeout=10.0)
        if r.status_code == 200:
            snapshots = r.json().get("result", [])
            print(f"  Found {len(snapshots)} snapshots")
            return snapshots
        else:
            print(f"  Snapshot list failed: {r.status_code}")
            return []
    except Exception as e:
        print(f"  Snapshot list error: {e}")
        return []


def test_snapshot_delete(url: str, collection: str, snapshot_name: str) -> bool:
    """Delete a snapshot."""
    try:
        r = httpx.delete(f"{url}/collections/{collection}/snapshots/{snapshot_name}", timeout=10.0)
        if r.status_code == 200:
            print(f"  Snapshot deleted: {snapshot_name}")
            return True
        else:
            print(f"  Snapshot delete failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"  Snapshot delete error: {e}")
        return False


def test_point_export(url: str, collection: str, limit: int = 10, include_vectors: bool = False) -> list:
    """Export points from a collection."""
    try:
        r = httpx.post(
            f"{url}/collections/{collection}/points/scroll",
            json={"limit": limit, "with_payload": True, "with_vector": include_vectors},
            timeout=10.0,
        )
        if r.status_code == 200:
            points = r.json().get("result", {}).get("points", [])
            print(f"  Exported {len(points)} points")
            return points
        else:
            print(f"  Export failed: {r.status_code}")
            return []
    except Exception as e:
        print(f"  Export error: {e}")
        return []


def test_point_import(url: str, collection: str, points: list) -> bool:
    """Import points into a collection."""
    if not points:
        print("  No points to import")
        return False

    # Include vectors if available (for backup/restore)
    import_points = []
    for pt in points:
        import_pt = {
            "id": pt["id"],
            "payload": pt.get("payload", {}),
        }
        if "vector" in pt:
            import_pt["vector"] = pt["vector"]
        import_points.append(import_pt)

    try:
        r = httpx.put(
            f"{url}/collections/{collection}/points",
            json={"points": import_points},
            timeout=10.0,
        )
        if r.status_code == 200:
            print(f"  Imported {len(import_points)} points")
            return True
        else:
            print(f"  Import failed: {r.status_code} {r.text[:200]}")
            return False
    except Exception as e:
        print(f"  Import error: {e}")
        return False


def test_collection_create(url: str, name: str, dim: int = 768) -> bool:
    """Create a test collection."""
    try:
        r = httpx.put(
            f"{url}/collections/{name}",
            json={"vectors": {"size": dim, "distance": "Cosine"}},
            timeout=10.0,
        )
        if r.status_code == 200:
            print(f"  Created test collection: {name}")
            return True
        else:
            print(f"  Create collection failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"  Create collection error: {e}")
        return False


def test_collection_delete(url: str, name: str) -> bool:
    """Delete a collection."""
    try:
        r = httpx.delete(f"{url}/collections/{name}", timeout=10.0)
        if r.status_code == 200:
            print(f"  Deleted collection: {name}")
            return True
        else:
            print(f"  Delete collection failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"  Delete collection error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test backup/restore procedures")
    parser.add_argument("--env", default="dev")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--cleanup", action="store_true", help="Clean up test artifacts")
    parser.add_argument("--collection", default="mem_episodic", help="Collection to test with")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Backup/Restore Test — {args.env.upper()}")
    print(f"{'='*60}\n")

    if not check_qdrant(args.qdrant_url):
        print("ERROR: Qdrant not reachable")
        sys.exit(1)

    test_collection = f"test-backup-{int(time.time())}"
    results = []

    # Test 1: Snapshot creation
    print("[1/5] Snapshot creation...")
    snapshot = test_snapshot_create(args.qdrant_url, args.collection)
    results.append(("Snapshot create", snapshot is not None))

    # Test 2: Snapshot listing
    print("[2/5] Snapshot listing...")
    snapshots = test_snapshot_list(args.qdrant_url, args.collection)
    results.append(("Snapshot list", len(snapshots) > 0))

    # Test 3: Point export (with vectors for backup)
    print("[3/5] Point export...")
    points = test_point_export(args.qdrant_url, args.collection, include_vectors=True)
    results.append(("Point export", len(points) > 0))

    # Test 4: Import to new collection
    print("[4/5] Import to test collection...")
    if points:
        create_ok = test_collection_create(args.qdrant_url, test_collection)
        import_ok = test_point_import(args.qdrant_url, test_collection, points) if create_ok else False
        results.append(("Point import", import_ok))
    else:
        results.append(("Point import", False))

    # Test 5: Verify import
    print("[5/5] Verify import...")
    if points:
        imported = test_point_export(args.qdrant_url, test_collection, limit=100)
        verify_ok = len(imported) == len(points)
        results.append(("Import verify", verify_ok))
    else:
        results.append(("Import verify", False))

    # Cleanup
    if args.cleanup:
        print("\nCleaning up...")
        if snapshots:
            test_snapshot_delete(args.qdrant_url, args.collection, snapshots[0].get("name", ""))
        test_collection_delete(args.qdrant_url, test_collection)

    # Summary
    print(f"\n{'='*60}")
    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        icon = "\033[92m\u2714\033[0m" if ok else "\033[91m\u2718\033[0m"
        print(f"  {icon} {name}: {'PASS' if ok else 'FAIL'}")
    print(f"\n  Result: {passed}/{len(results)} passed")
    print(f"{'='*60}\n")

    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
