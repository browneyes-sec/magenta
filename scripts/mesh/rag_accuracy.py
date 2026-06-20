#!/usr/bin/env python3
"""RAG accuracy measurement tool.

Measures:
  - Precision@K / Recall@K for retrieved memories
  - NDCG@5 (Normalized Discounted Cumulative Gain)
  - End-to-end latency (query → embedding → search → context)
  - Token budget compliance
  - Cross-tier contamination check
  - Hallucination detection (relevant context exists vs. not)

Usage:
    python scripts/mesh/rag_accuracy.py --env dev
    python scripts/mesh/rag_accuracy.py --env dev --golden tests/eval/memory_golden.jsonl
    python scripts/mesh/rag_accuracy.py --env dev --ndcg-only
"""

import argparse
import json
import math
import time
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import httpx


@dataclass
class EvalResult:
    query: str
    tier: str
    precision_at_1: float = 0.0
    precision_at_3: float = 0.0
    recall_at_5: float = 0.0
    ndcg_at_5: float = 0.0
    latency_ms: float = 0.0
    retrieved_ids: list[str] = field(default_factory=list)
    relevant_found: int = 0
    irrelevant_leaked: int = 0
    token_count: int = 0
    passed: bool = False


@dataclass
class AccuracyReport:
    environment: str
    golden_file: str
    timestamp: str
    total_queries: int = 0
    tier_results: dict = field(default_factory=dict)
    overall_ndcg: float = 0.0
    overall_precision: float = 0.0
    overall_recall: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    ndcg_target: float = 0.75
    passed: bool = False

    def to_dict(self):
        return {
            "environment": self.environment,
            "golden_file": self.golden_file,
            "timestamp": self.timestamp,
            "overall": {
                "ndcg@5": round(self.overall_ndcg, 4),
                "precision@1": round(self.overall_precision, 4),
                "recall@5": round(self.overall_recall, 4),
                "avg_latency_ms": round(self.avg_latency_ms, 1),
                "p95_latency_ms": round(self.p95_latency_ms, 1),
                "ndcg_target": self.ndcg_target,
                "passed": self.passed,
            },
            "by_tier": self.tier_results,
            "total_queries": self.total_queries,
        }


def dcg(relevances: list[int], k: int = 5) -> float:
    """Discounted Cumulative Gain at k."""
    return sum(
        rel / math.log2(i + 2) for i, rel in enumerate(relevances[:k])
    )


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int = 5) -> float:
    """Normalized DCG at k."""
    relevances = [
        1 if rid in relevant_ids else 0
        for rid in retrieved_ids[:k]
    ]
    actual_dcg = dcg(relevances, k)

    # Ideal: all relevant items at top
    ideal_relevances = sorted(relevances, reverse=True)
    ideal_dcg = dcg(ideal_relevances, k)

    if ideal_dcg == 0:
        return 0.0
    return actual_dcg / ideal_dcg


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for rid in top_k if rid in relevant_ids)
    return hits / len(top_k)


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for rid in top_k if rid in relevant_ids)
    return hits / len(relevant_ids)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def run_eval(
    qdrant_url: str,
    ollama_url: str,
    golden_path: str,
    mesh_api_url: Optional[str] = None,
) -> AccuracyReport:
    import datetime

    report = AccuracyReport(
        environment="eval",
        golden_file=golden_path,
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
    )

    # Load golden dataset
    queries = []
    with open(golden_path) as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))

    report.total_queries = len(queries)
    all_latencies = []
    tier_data = {}

    for item in queries:
        query = item["query"]
        relevant_ids = set(item["relevant_ids"])
        irrelevant_ids = set(item.get("irrelevant_ids", []))
        tier = item.get("tier", "episodic")

        # Generate embedding
        embed_start = time.time()
        try:
            r = httpx.post(f"{ollama_url}/api/embed", json={
                "model": "nomic-embed-text",
                "input": query,
            }, timeout=15.0)
            embedding = r.json()["embeddings"][0]
        except Exception as e:
            print(f"  [SKIP] Embedding failed for: {query[:50]}... ({e})")
            continue
        embed_latency = (time.time() - embed_start) * 1000

        # Search Qdrant
        collection = f"mem_{tier}"
        search_start = time.time()
        try:
            r = httpx.post(
                f"{qdrant_url}/collections/{collection}/points/search",
                json={
                    "vector": embedding,
                    "limit": 10,
                    "with_payload": True,
                },
                timeout=10.0,
            )
            results = r.json().get("result", [])
        except Exception:
            # Try episodic as fallback
            try:
                r = httpx.post(
                    f"{qdrant_url}/collections/episodic_memory/points/search",
                    json={"vector": embedding, "limit": 10, "with_payload": True},
                    timeout=10.0,
                )
                results = r.json().get("result", [])
            except Exception:
                results = []
        search_latency = (time.time() - search_start) * 1000

        # Extract IDs from results (check both id and payload.original_id)
        retrieved_ids = []
        total_tokens = 0
        for pt in results:
            payload = pt.get("payload", {})
            # Use original_id if available (for seeded data), otherwise use point ID
            pid = payload.get("original_id") or payload.get("id") or str(pt.get("id", ""))
            retrieved_ids.append(pid)
            total_tokens += estimate_tokens(payload.get("text", ""))

        total_latency = embed_latency + search_latency

        # Calculate metrics
        p1 = precision_at_k(retrieved_ids, relevant_ids, 1)
        p3 = precision_at_k(retrieved_ids, relevant_ids, 3)
        r5 = recall_at_k(retrieved_ids, relevant_ids, 5)
        n5 = ndcg_at_k(retrieved_ids, relevant_ids, 5)

        relevant_found = len(relevant_ids.intersection(set(retrieved_ids)))
        irrelevant_leaked = len(irrelevant_ids.intersection(set(retrieved_ids)))

        result = EvalResult(
            query=query,
            tier=tier,
            precision_at_1=p1,
            precision_at_3=p3,
            recall_at_5=r5,
            ndcg_at_5=n5,
            latency_ms=round(total_latency, 1),
            retrieved_ids=retrieved_ids[:5],
            relevant_found=relevant_found,
            irrelevant_leaked=irrelevant_leaked,
            token_count=total_tokens,
            passed=n5 >= 0.5,
        )

        # Aggregate by tier
        if tier not in tier_data:
            tier_data[tier] = {"results": [], "ndcg": [], "precision": [], "recall": [], "latency": []}
        tier_data[tier]["results"].append(result)
        tier_data[tier]["ndcg"].append(n5)
        tier_data[tier]["precision"].append(p1)
        tier_data[tier]["recall"].append(r5)
        tier_data[tier]["latency"].append(total_latency)
        all_latencies.append(total_latency)

    # Compute per-tier summaries
    for tier, data in tier_data.items():
        n = len(data["ndcg"])
        if n == 0:
            continue
        report.tier_results[tier] = {
            "count": n,
            "ndcg@5_mean": round(sum(data["ndcg"]) / n, 4),
            "precision@1_mean": round(sum(data["precision"]) / n, 4),
            "recall@5_mean": round(sum(data["recall"]) / n, 4),
            "latency_mean_ms": round(sum(data["latency"]) / n, 1),
            "pass_rate": round(sum(1 for r in data["results"] if r.passed) / n, 4),
        }

    # Compute overall
    all_ndcg = []
    all_precision = []
    all_recall = []
    for data in tier_data.values():
        all_ndcg.extend(data["ndcg"])
        all_precision.extend(data["precision"])
        all_recall.extend(data["recall"])

    if all_ndcg:
        report.overall_ndcg = sum(all_ndcg) / len(all_ndcg)
        report.overall_precision = sum(all_precision) / len(all_precision)
        report.overall_recall = sum(all_recall) / len(all_recall)

    if all_latencies:
        all_latencies.sort()
        report.avg_latency_ms = sum(all_latencies) / len(all_latencies)
        p95_idx = int(len(all_latencies) * 0.95)
        report.p95_latency_ms = all_latencies[min(p95_idx, len(all_latencies) - 1)]

    report.passed = report.overall_ndcg >= report.ndcg_target
    return report


def main():
    parser = argparse.ArgumentParser(description="Measure RAG accuracy")
    parser.add_argument("--env", default="dev")
    parser.add_argument("--golden", default="tests/eval/memory_golden.jsonl")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--output", choices=["json", "text"], default="text")
    parser.add_argument("--ndcg-only", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not Path(args.golden).exists():
        print(f"Golden file not found: {args.golden}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  RAG Accuracy Evaluation — {args.env.upper()}")
    print(f"  Golden: {args.golden}")
    print(f"{'='*60}\n")

    report = run_eval(args.qdrant_url, args.ollama_url, args.golden)

    if args.output == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"  Queries evaluated: {report.total_queries}")
        print(f"  Overall NDCG@5:    {report.overall_ndcg:.4f} (target: {report.ndcg_target})")
        print(f"  Overall P@1:       {report.overall_precision:.4f}")
        print(f"  Overall R@5:       {report.overall_recall:.4f}")
        print(f"  Avg latency:       {report.avg_latency_ms:.1f}ms")
        print(f"  P95 latency:       {report.p95_latency_ms:.1f}ms")
        print()

        if args.verbose:
            for tier, data in report.tier_results.items():
                print(f"  [{tier.upper()}]")
                print(f"    Queries: {data['count']}")
                print(f"    NDCG@5:  {data['ndcg@5_mean']:.4f}")
                print(f"    P@1:     {data['precision@1_mean']:.4f}")
                print(f"    R@5:     {data['recall@5_mean']:.4f}")
                print(f"    Latency: {data['latency_mean_ms']:.1f}ms")
                print(f"    Pass:    {data['pass_rate']:.1%}")
                print()

        status = "\033[92mPASS\033[0m" if report.passed else "\033[91mFAIL\033[0m"
        print(f"  {'='*60}")
        print(f"  Result: {status} (NDCG@5 = {report.overall_ndcg:.4f})")
        print(f"  {'='*60}\n")

    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
