#!/usr/bin/env python3
"""Load testing for memory infrastructure.

Tests:
  1. Write throughput (points/second)
  2. Search throughput (queries/second)
  3. Latency distribution (p50, p95, p99)
  4. Concurrent client simulation
  5. Memory collection size impact

Usage:
    python scripts/mesh/load_test.py --env dev
    python scripts/mesh/load_test.py --env dev --duration 60 --qps 10
"""

import argparse
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx


TEST_QUERIES = [
    "ransomware alert on endpoint",
    "phishing email detected",
    "firewall rule change",
    "suspicious login attempt",
    "malware outbreak containment",
    "DDoS attack mitigation",
    "data exfiltration attempt",
    "insider threat detection",
    "vulnerability scan results",
    "incident response procedure",
]


def generate_test_point(index: int) -> dict:
    """Generate a test point for loading."""
    query = random.choice(TEST_QUERIES)
    return {
        "text": f"Load test point {index}: {query} with additional context for realistic embedding",
        "metadata": {
            "agent_role": "load-test",
            "mission_id": f"LOAD-{index % 100}",
            "tenant_id": "load-test",
            "memory_type": "episodic",
            "source_tool": "load_test.py",
            "created_at": int(time.time() * 1000),
        },
    }


def embed_text(ollama_url: str, text: str) -> list[float]:
    """Generate embedding."""
    r = httpx.post(f"{ollama_url}/api/embed", json={
        "model": "nomic-embed-text",
        "input": text,
    }, timeout=30.0)
    return r.json()["embeddings"][0]


def write_point(qdrant_url: str, collection: str, point: dict, vector: list[float]) -> bool:
    """Write a single point to Qdrant."""
    import uuid
    r = httpx.put(
        f"{qdrant_url}/collections/{collection}/points",
        json={"points": [{"id": str(uuid.uuid4()), "vector": vector, "payload": point["metadata"]}]},
        timeout=10.0,
    )
    return r.status_code == 200


def search_point(qdrant_url: str, collection: str, vector: list[float]) -> bool:
    """Search for a point in Qdrant."""
    r = httpx.post(
        f"{qdrant_url}/collections/{collection}/points/search",
        json={"vector": vector, "limit": 5},
        timeout=10.0,
    )
    return r.status_code == 200


def test_write_throughput(qdrant_url: str, ollama_url: str, collection: str,
                          duration: int, concurrency: int) -> dict:
    """Test write throughput."""
    print(f"  Write test: {duration}s, {concurrency} concurrent writers")

    latencies = []
    errors = 0
    start = time.time()

    def write_worker(worker_id: int):
        nonlocal errors
        worker_latencies = []
        client = httpx.Client(timeout=30.0)
        while time.time() - start < duration:
            try:
                point = generate_test_point(worker_id * 1000 + len(worker_latencies))
                embed_start = time.time()
                r = client.post(f"{ollama_url}/api/embed", json={
                    "model": "nomic-embed-text",
                    "input": point["text"],
                })
                vector = r.json()["embeddings"][0]
                embed_latency = (time.time() - embed_start) * 1000

                write_start = time.time()
                import uuid
                r = client.put(
                    f"{qdrant_url}/collections/{collection}/points",
                    json={"points": [{"id": str(uuid.uuid4()), "vector": vector, "payload": point["metadata"]}]},
                )
                write_latency = (time.time() - write_start) * 1000

                if r.status_code == 200:
                    worker_latencies.append(embed_latency + write_latency)
                else:
                    errors += 1
            except Exception:
                errors += 1
        return worker_latencies

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(write_worker, i) for i in range(concurrency)]
        for future in as_completed(futures):
            latencies.extend(future.result())

    elapsed = time.time() - start
    throughput = len(latencies) / elapsed if elapsed > 0 else 0

    return {
        "total_writes": len(latencies),
        "errors": errors,
        "duration_s": round(elapsed, 1),
        "throughput_qps": round(throughput, 1),
        "latency_p50_ms": round(statistics.median(latencies), 1) if latencies else 0,
        "latency_p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 1) if latencies else 0,
        "latency_p99_ms": round(sorted(latencies)[int(len(latencies) * 0.99)], 1) if latencies else 0,
    }


def test_search_throughput(qdrant_url: str, ollama_url: str, collection: str,
                           duration: int, concurrency: int) -> dict:
    """Test search throughput."""
    print(f"  Search test: {duration}s, {concurrency} concurrent searchers")

    latencies = []
    errors = 0
    start = time.time()

    def search_worker(worker_id: int):
        nonlocal errors
        worker_latencies = []
        client = httpx.Client(timeout=30.0)
        while time.time() - start < duration:
            try:
                query = random.choice(TEST_QUERIES)
                embed_start = time.time()
                r = client.post(f"{ollama_url}/api/embed", json={
                    "model": "nomic-embed-text",
                    "input": query,
                })
                vector = r.json()["embeddings"][0]
                embed_latency = (time.time() - embed_start) * 1000

                search_start = time.time()
                r = client.post(
                    f"{qdrant_url}/collections/{collection}/points/search",
                    json={"vector": vector, "limit": 5},
                )
                search_latency = (time.time() - search_start) * 1000

                if r.status_code == 200:
                    worker_latencies.append(embed_latency + search_latency)
                else:
                    errors += 1
            except Exception:
                errors += 1
        return worker_latencies

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(search_worker, i) for i in range(concurrency)]
        for future in as_completed(futures):
            latencies.extend(future.result())

    elapsed = time.time() - start
    throughput = len(latencies) / elapsed if elapsed > 0 else 0

    return {
        "total_searches": len(latencies),
        "errors": errors,
        "duration_s": round(elapsed, 1),
        "throughput_qps": round(throughput, 1),
        "latency_p50_ms": round(statistics.median(latencies), 1) if latencies else 0,
        "latency_p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 1) if latencies else 0,
        "latency_p99_ms": round(sorted(latencies)[int(len(latencies) * 0.99)], 1) if latencies else 0,
    }


def check_collection_size(qdrant_url: str, collection: str) -> dict:
    """Check collection size metrics."""
    try:
        r = httpx.get(f"{qdrant_url}/collections/{collection}", timeout=10.0)
        info = r.json().get("result", {})
        return {
            "points_count": info.get("points_count", 0),
            "indexed_vectors_count": info.get("indexed_vectors_count", 0),
            "status": info.get("status", "unknown"),
        }
    except Exception:
        return {"points_count": 0, "indexed_vectors_count": 0, "status": "error"}


def main():
    parser = argparse.ArgumentParser(description="Load test memory infrastructure")
    parser.add_argument("--env", default="dev")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--collection", default="mem_episodic")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    parser.add_argument("--qps", type=int, default=5, help="Target queries per second per worker")
    parser.add_argument("--workers", type=int, default=2, help="Number of concurrent workers")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Load Test — {args.env.upper()}")
    print(f"  Duration: {args.duration}s | Workers: {args.workers}")
    print(f"{'='*60}\n")

    # Check services
    try:
        r = httpx.get(f"{args.qdrant_url}/healthz", timeout=5.0)
        if r.status_code != 200:
            print("ERROR: Qdrant not reachable")
            sys.exit(1)
    except Exception:
        print("ERROR: Qdrant not reachable")
        sys.exit(1)

    # Initial size
    print("Initial collection size:")
    initial_size = check_collection_size(args.qdrant_url, args.collection)
    print(f"  Points: {initial_size['points_count']}\n")

    # Write test
    print("[1/2] Write throughput test...")
    write_results = test_write_throughput(
        args.qdrant_url, args.ollama_url, args.collection,
        args.duration, args.workers,
    )

    # Search test
    print("[2/2] Search throughput test...")
    search_results = test_search_throughput(
        args.qdrant_url, args.ollama_url, args.collection,
        args.duration, args.workers,
    )

    # Final size
    print("\nFinal collection size:")
    final_size = check_collection_size(args.qdrant_url, args.collection)
    print(f"  Points: {final_size['points_count']} (+{final_size['points_count'] - initial_size['points_count']})")

    # Summary
    print(f"\n{'='*60}")
    print(f"  Load Test Results")
    print(f"{'='*60}")
    print(f"\n  Write:")
    print(f"    Throughput: {write_results['throughput_qps']} writes/s")
    print(f"    Latency p50: {write_results['latency_p50_ms']}ms")
    print(f"    Latency p95: {write_results['latency_p95_ms']}ms")
    print(f"    Latency p99: {write_results['latency_p99_ms']}ms")
    print(f"    Errors: {write_results['errors']}")
    print(f"\n  Search:")
    print(f"    Throughput: {search_results['throughput_qps']} searches/s")
    print(f"    Latency p50: {search_results['latency_p50_ms']}ms")
    print(f"    Latency p95: {search_results['latency_p95_ms']}ms")
    print(f"    Latency p99: {search_results['latency_p99_ms']}ms")
    print(f"    Errors: {search_results['errors']}")
    print(f"\n  {'='*60}")

    # Pass/Fail
    write_ok = write_results['latency_p99_ms'] < 1000 and write_results['errors'] == 0
    search_ok = search_results['latency_p99_ms'] < 500 and search_results['errors'] == 0
    status = "PASS" if (write_ok and search_ok) else "FAIL"
    print(f"  Result: {status}")
    print(f"{'='*60}\n")

    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
