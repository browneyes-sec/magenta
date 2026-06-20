#!/usr/bin/env python3
"""Deploy and validate Magenta memory infrastructure (ADR-018).

Orchestrates:
  1. Check Qdrant/OLLAMA reachability
  2. Create Qdrant collections
  3. Pull OLLAMA embedding model
  4. Seed golden eval data
  5. Validate memory health
  6. Measure RAG accuracy

Usage:
    python scripts/mesh/deploy_memory.py --env dev
    python scripts/mesh/deploy_memory.py --env dev --skip-pull
    python scripts/mesh/deploy_memory.py --env dev --seed-only
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx


ENVIRONMENTS = {
    "dev": {
        "qdrant": "http://localhost:6333",
        "ollama": "http://localhost:11434",
    },
    "staging": {
        "qdrant": "http://qdrant-staging:6333",
        "ollama": "http://ollama-staging:11434",
    },
    "prod": {
        "qdrant": "http://qdrant-prod:6333",
        "ollama": "http://ollama-prod:11434",
    },
}


def check_service(name: str, url: str, path: str = "/healthz") -> bool:
    """Check if a service is reachable."""
    try:
        r = httpx.get(f"{url}{path}", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


def run_script(script: str, args: list[str]) -> bool:
    """Run a setup script and return success."""
    script_path = Path(__file__).parent / script
    cmd = [sys.executable, str(script_path)] + args
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Deploy memory infrastructure")
    parser.add_argument("--env", default="dev")
    parser.add_argument("--qdrant-url", help="Override Qdrant URL")
    parser.add_argument("--ollama-url", help="Override OLLAMA URL")
    parser.add_argument("--skip-pull", action="store_true", help="Skip model pull")
    parser.add_argument("--skip-seed", action="store_true", help="Skip eval data seeding")
    parser.add_argument("--skip-validate", action="store_true", help="Skip health validation")
    parser.add_argument("--skip-accuracy", action="store_true", help="Skip RAG accuracy")
    parser.add_argument("--seed-only", action="store_true", help="Only seed eval data")
    parser.add_argument("--force", action="store_true", help="Force recreate collections")
    args = parser.parse_args()

    config = ENVIRONMENTS.get(args.env, ENVIRONMENTS["dev"])
    qdrant_url = args.qdrant_url or config["qdrant"]
    ollama_url = args.ollama_url or config["ollama"]

    print(f"\n{'='*60}")
    print(f"  Magenta Memory Deployment — {args.env.upper()}")
    print(f"{'='*60}\n")

    steps = []
    start_time = time.time()

    # Step 1: Check services
    print("[1/6] Checking services...")
    qdrant_ok = check_service("Qdrant", qdrant_url)
    ollama_ok = check_service("OLLAMA", ollama_url, "/api/tags")
    steps.append(("Service check", qdrant_ok and ollama_ok))

    if not qdrant_ok:
        print(f"  ERROR: Qdrant not reachable at {qdrant_url}")
        print("  Start Qdrant: docker start magenta-qdrant")
    if not ollama_ok:
        print(f"  ERROR: OLLAMA not reachable at {ollama_url}")
        print("  Start OLLAMA: docker start magenta-ollama")

    if not (qdrant_ok and ollama_ok):
        print("\n  Cannot proceed without running services.")
        sys.exit(1)

    print("  Qdrant: OK")
    print("  OLLAMA: OK\n")

    if args.seed_only:
        # Skip to seeding
        print("[2/6] Skipping (seed-only mode)")
        print("[3/6] Skipping (seed-only mode)")
        print("[4/6] Seeding eval data...")
        seed_ok = run_script("seed_eval_data.py", ["--env", args.env, "--clear-first"])
        steps.append(("Seed eval data", seed_ok))
        print(f"\n{'='*60}")
        print(f"  Seed-only complete")
        print(f"{'='*60}\n")
        sys.exit(0 if seed_ok else 1)

    # Step 2: Create collections
    print("[2/6] Creating Qdrant collections...")
    collection_args = ["--env", args.env, "--indexes"]
    if args.force:
        collection_args.append("--force")
    collections_ok = run_script("setup_collections.py", collection_args)
    steps.append(("Create collections", collections_ok))
    print()

    # Step 3: Pull models
    if not args.skip_pull:
        print("[3/6] Pulling OLLAMA models...")
        pull_args = ["--env", args.env, "--verify"]
        pull_ok = run_script("pull_models.py", pull_args)
        steps.append(("Pull models", pull_ok))
    else:
        print("[3/6] Skipping model pull (--skip-pull)")
        pull_ok = True
    print()

    # Step 4: Seed eval data
    if not args.skip_seed:
        print("[4/6] Seeding eval data...")
        seed_ok = run_script("seed_eval_data.py", ["--env", args.env, "--clear-first"])
        steps.append(("Seed eval data", seed_ok))
    else:
        print("[4/6] Skipping seed (--skip-seed)")
        seed_ok = True
    print()

    # Step 5: Validate memory
    if not args.skip_validate:
        print("[5/6] Validating memory health...")
        validate_args = ["--env", args.env, "--verbose", "--write-test"]
        validate_ok = run_script("validate_memory.py", validate_args)
        steps.append(("Validate memory", validate_ok))
    else:
        print("[5/6] Skipping validation (--skip-validate)")
        validate_ok = True
    print()

    # Step 6: RAG accuracy
    if not args.skip_accuracy:
        print("[6/6] Measuring RAG accuracy...")
        accuracy_args = ["--env", args.env, "--verbose"]
        accuracy_ok = run_script("rag_accuracy.py", accuracy_args)
        steps.append(("RAG accuracy", accuracy_ok))
    else:
        print("[6/6] Skipping accuracy (--skip-accuracy)")
        accuracy_ok = True
    print()

    # Summary
    elapsed = time.time() - start_time
    passed = sum(1 for _, ok in steps if ok)
    total = len(steps)

    print(f"{'='*60}")
    print(f"  Deployment Summary")
    print(f"{'='*60}")
    for name, ok in steps:
        status = "PASS" if ok else "FAIL"
        icon = "\033[92m\u2714\033[0m" if ok else "\033[91m\u2718\033[0m"
        print(f"  {icon} {name}: {status}")
    print(f"\n  Elapsed: {elapsed:.1f}s")
    print(f"  Result: {passed}/{total} steps passed")
    print(f"{'='*60}\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
