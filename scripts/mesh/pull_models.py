#!/usr/bin/env python3
"""Pull required OLLAMA models for Magenta memory (ADR-018).

Pulls:
- bge-m3: Embedding model (1024-dim) for memory search
- qwen2.5:0.5b: LLM for MVS tier (397MB)
- qwen2.5:1.5b: LLM for small agents (986MB, optional)

Usage:
    python scripts/mesh/pull_models.py --env dev
    python scripts/mesh/pull_models.py --env dev --model bge-m3
    python scripts/mesh/pull_models.py --env dev --all
"""

import argparse
import sys
import time

import httpx


MODELS = {
    "bge-m3": {
        "description": "Embedding model (1024-dim, multilingual)",
        "required": True,
        "size_mb": 1200,
    },
    "qwen2.5:0.5b": {
        "description": "LLM for MVS tier (397MB)",
        "required": True,
        "size_mb": 397,
    },
    "qwen2.5:1.5b": {
        "description": "LLM for small agents (986MB)",
        "required": False,
        "size_mb": 986,
    },
}

ENVIRONMENTS = {
    "dev": {
        "ollama": "http://localhost:11434",
    },
    "staging": {
        "ollama": "http://ollama-staging:11434",
    },
    "prod": {
        "ollama": "http://ollama-prod:11434",
    },
}


def check_ollama(url: str) -> bool:
    """Check OLLAMA is reachable."""
    try:
        r = httpx.get(f"{url}/api/tags", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


def list_models(url: str) -> list[str]:
    """List pulled models."""
    try:
        r = httpx.get(f"{url}/api/tags", timeout=5.0)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def pull_model(url: str, model: str, timeout: int = 600) -> bool:
    """Pull a model from OLLAMA registry."""
    print(f"  [{model}] Pulling... ", end="", flush=True)
    try:
        r = httpx.post(
            f"{url}/api/pull",
            json={"name": model},
            timeout=timeout,
        )
        if r.status_code == 200:
            print("OK")
            return True
        else:
            print(f"Failed: {r.status_code}")
            return False
    except httpx.TimeoutException:
        print("Timeout (model may be large)")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def verify_embedding(url: str, model: str) -> bool:
    """Verify embedding model works by generating a test embedding."""
    print(f"  [{model}] Verifying embedding... ", end="", flush=True)
    try:
        r = httpx.post(
            f"{url}/api/embed",
            json={"model": model, "input": "test"},
            timeout=30.0,
        )
        if r.status_code == 200:
            embeddings = r.json().get("embeddings", [])
            if embeddings and len(embeddings[0]) == 1024:
                print(f"OK (dim={len(embeddings[0])})")
                return True
            else:
                print(f"Unexpected dim: {len(embeddings[0]) if embeddings else 0}")
                return False
        else:
            print(f"Failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Pull OLLAMA models")
    parser.add_argument("--env", default="dev")
    parser.add_argument("--ollama-url", help="Override OLLAMA URL")
    parser.add_argument("--model", help="Pull specific model")
    parser.add_argument("--all", action="store_true", help="Pull all models")
    parser.add_argument("--verify", action="store_true", help="Verify embeddings")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = ENVIRONMENTS.get(args.env, ENVIRONMENTS["dev"])
    ollama_url = args.ollama_url or config["ollama"]

    print(f"\n{'='*60}")
    print(f"  OLLAMA Model Pull — {args.env.upper()}")
    print(f"  URL: {ollama_url}")
    print(f"{'='*60}\n")

    # Check OLLAMA
    if not args.dry_run and not check_ollama(ollama_url):
        print(f"  ERROR: OLLAMA not reachable at {ollama_url}")
        sys.exit(1)

    # Determine models to pull
    if args.model:
        models_to_pull = {args.model: MODELS.get(args.model, {"description": "Custom model", "required": True})}
    elif args.all:
        models_to_pull = MODELS
    else:
        # Pull required models only
        models_to_pull = {k: v for k, v in MODELS.items() if v["required"]}

    # List existing
    existing = list_models(ollama_url) if not args.dry_run else []
    if existing:
        print(f"  Existing models: {', '.join(existing)}\n")

    # Pull models
    success = 0
    for name, info in models_to_pull.items():
        if name in existing and not args.dry_run:
            print(f"  [{name}] Already pulled, skipping")
            success += 1
            continue

        if args.dry_run:
            print(f"  [{name}] Would pull: {info['description']}")
            success += 1
        else:
            print(f"  [{name}] {info['description']}")
            if pull_model(ollama_url, name):
                success += 1

    # Verify embeddings
    if args.verify and not args.dry_run:
        print("\nVerifying embedding models...")
        for name in models_to_pull:
            if "embed" in name.lower() or name == "bge-m3":
                verify_embedding(ollama_url, name)

    print(f"\n{'='*60}")
    print(f"  Result: {success}/{len(models_to_pull)} models ready")
    print(f"{'='*60}\n")

    sys.exit(0 if success == len(models_to_pull) else 1)


if __name__ == "__main__":
    main()
