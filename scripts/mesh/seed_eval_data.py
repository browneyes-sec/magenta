#!/usr/bin/env python3
"""Seed Qdrant with test data for RAG accuracy evaluation.

Creates test vectors with known relevance labels so we can measure
precision, recall, and NDCG@5 against a golden dataset.

Usage:
    python scripts/mesh/seed_eval_data.py --env dev
    python scripts/mesh/seed_eval_data.py --env dev --clear-first
"""

import argparse
import json
import time
import uuid
from pathlib import Path

import httpx

GOLDEN_FILE = "tests/eval/memory_golden.jsonl"

COLLECTIONS = {
    "mem_episodic": [],
    "mem_semantic": [],
    "mem_procedural": [],
}


def load_golden_data():
    """Load golden dataset and categorize by tier."""
    queries = []
    with open(GOLDEN_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def generate_test_points(queries):
    """Generate test points from golden dataset entries."""
    points = {
        "mem_episodic": [],
        "mem_semantic": [],
        "mem_procedural": [],
    }

    # Map string IDs to UUIDs for Qdrant compatibility
    id_map = {}

    for item in queries:
        tier = item.get("tier", "episodic")
        collection = f"mem_{tier}"

        # Create points for relevant IDs
        for rid in item.get("relevant_ids", []):
            if rid not in id_map:
                id_map[rid] = str(uuid.uuid5(uuid.NAMESPACE_DNS, rid))
            points[collection].append(
                {
                    "id": id_map[rid],
                    "original_id": rid,
                    "text": f"Test content for query: {item['query']}. "
                    f"This is a relevant {tier} memory about: {item['expected_answer'][:100]}",
                    "metadata": {
                        "agent_role": "validator",
                        "mission_id": "eval-seed",
                        "tenant_id": "eval-test",
                        "memory_type": tier,
                        "source_tool": "seed_eval_data.py",
                        "created_at": int(time.time() * 1000),
                        "relevance": "relevant",
                        "original_query": item["query"],
                    },
                }
            )

        # Create points for irrelevant IDs
        for rid in item.get("irrelevant_ids", []):
            if rid not in id_map:
                id_map[rid] = str(uuid.uuid5(uuid.NAMESPACE_DNS, rid))
            points[collection].append(
                {
                    "id": id_map[rid],
                    "original_id": rid,
                    "text": f"Unrelated content about network monitoring, "
                    f"firewall rules, and endpoint security. Not related to: {item['query'][:50]}",
                    "metadata": {
                        "agent_role": "validator",
                        "mission_id": "eval-seed",
                        "tenant_id": "eval-test",
                        "memory_type": tier,
                        "source_tool": "seed_eval_data.py",
                        "created_at": int(time.time() * 1000),
                        "relevance": "irrelevant",
                    },
                }
            )

    return points, id_map


def embed_text(ollama_url: str, text: str) -> list[float]:
    """Generate embedding using OLLAMA."""
    r = httpx.post(
        f"{ollama_url}/api/embed",
        json={
            "model": "nomic-embed-text",
            "input": text,
        },
        timeout=30.0,
    )
    return r.json()["embeddings"][0]


def seed_collection(qdrant_url: str, ollama_url: str, collection: str, points: list):
    """Embed and insert points into Qdrant."""
    if not points:
        print(f"  [{collection}] No points to seed")
        return 0

    embedded_points = []
    for i, pt in enumerate(points):
        try:
            embedding = embed_text(ollama_url, pt["text"])
            # Include original_id in payload for accuracy measurement
            payload = pt["metadata"].copy()
            payload["original_id"] = pt["original_id"]
            embedded_points.append(
                {
                    "id": pt["id"],
                    "vector": embedding,
                    "payload": payload,
                    "payload_text": pt["text"],  # store full text in payload
                }
            )
            if (i + 1) % 10 == 0:
                print(f"  [{collection}] Embedded {i + 1}/{len(points)}")
        except Exception as e:
            print(f"  [{collection}] Failed to embed {pt['id']}: {e}")

    if not embedded_points:
        return 0

    # Batch upsert (max 100 per batch)
    batch_size = 100
    total_inserted = 0
    for i in range(0, len(embedded_points), batch_size):
        batch = embedded_points[i : i + batch_size]
        try:
            r = httpx.put(
                f"{qdrant_url}/collections/{collection}/points",
                json={
                    "points": [
                        {
                            "id": p["id"],
                            "vector": p["vector"],
                            "payload": {
                                **p["payload"],
                                "text": p["payload_text"],
                            },
                        }
                        for p in batch
                    ]
                },
                timeout=30.0,
            )
            if r.status_code == 200:
                total_inserted += len(batch)
            else:
                print(f"  [{collection}] Batch insert failed: {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"  [{collection}] Batch insert error: {e}")

    return total_inserted


def clear_collection(qdrant_url: str, collection: str):
    """Delete all points in a collection."""
    try:
        r = httpx.post(
            f"{qdrant_url}/collections/{collection}/points/delete",
            json={"filter": {"must": []}},  # match all
            timeout=30.0,
        )
        if r.status_code == 200:
            print(f"  [{collection}] Cleared")
        else:
            print(f"  [{collection}] Clear failed: {r.status_code}")
    except Exception as e:
        print(f"  [{collection}] Clear error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Seed eval data into Qdrant")
    parser.add_argument("--env", default="dev")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--clear-first", action="store_true")
    args = parser.parse_args()

    if not Path(GOLDEN_FILE).exists():
        print(f"Golden file not found: {GOLDEN_FILE}")
        exit(1)

    print(f"\n{'=' * 60}")
    print(f"  Seeding Eval Data — {args.env.upper()}")
    print(f"{'=' * 60}\n")

    # Load and categorize
    queries = load_golden_data()
    points, id_map = generate_test_points(queries)

    for collection, pts in points.items():
        print(f"  [{collection}] {len(pts)} points to seed")

    # Clear if requested
    if args.clear_first:
        print("\nClearing existing data...")
        for collection in points:
            clear_collection(args.qdrant_url, collection)

    # Seed each collection
    print("\nSeeding collections...")
    total = 0
    for collection, pts in points.items():
        inserted = seed_collection(args.qdrant_url, args.ollama_url, collection, pts)
        print(f"  [{collection}] Inserted: {inserted}/{len(pts)}")
        total += inserted

    print(f"\n{'=' * 60}")
    print(f"  Total seeded: {total} points")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
