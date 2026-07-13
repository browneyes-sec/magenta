"""Qdrant Collection Management — auto-create collections with HNSW per data mesh spec."""

from __future__ import annotations

import logging
from typing import Any

from magenta.mesh.config import MeshConfig

logger = logging.getLogger(__name__)

COLLECTIONS: dict[str, dict[str, Any]] = {
    "siem_alerts": {
        "vectors": {"size": 1024, "distance": "Cosine"},
        "hnsw_config": {"m": 16, "ef_construct": 200},
        "optimizers_config": {"default_segment_number": 2, "memmap_threshold_kb": 20000},
    },
    "mem_episodic": {
        "vectors": {"size": 1024, "distance": "Cosine"},
        "hnsw_config": {"m": 16, "ef_construct": 200},
        "optimizers_config": {"default_segment_number": 2, "memmap_threshold_kb": 20000},
    },
    "mem_semantic": {
        "vectors": {"size": 1024, "distance": "Cosine"},
        "hnsw_config": {"m": 16, "ef_construct": 200},
        "optimizers_config": {"default_segment_number": 2, "memmap_threshold_kb": 20000},
    },
    "mem_procedural": {
        "vectors": {"size": 1024, "distance": "Cosine"},
        "hnsw_config": {"m": 16, "ef_construct": 200},
        "optimizers_config": {"default_segment_number": 2, "memmap_threshold_kb": 20000},
    },
    "endpoint_windows": {
        "vectors": {"size": 1024, "distance": "Cosine"},
        "hnsw_config": {"m": 16, "ef_construct": 200},
        "optimizers_config": {"default_segment_number": 2, "memmap_threshold_kb": 20000},
    },
    "endpoint_linux": {
        "vectors": {"size": 1024, "distance": "Cosine"},
        "hnsw_config": {"m": 16, "ef_construct": 200},
        "optimizers_config": {"default_segment_number": 2, "memmap_threshold_kb": 20000},
    },
    "cloud_azure": {
        "vectors": {"size": 1024, "distance": "Cosine"},
        "hnsw_config": {"m": 16, "ef_construct": 200},
        "optimizers_config": {"default_segment_number": 2, "memmap_threshold_kb": 20000},
    },
    "cloud_aws": {
        "vectors": {"size": 1024, "distance": "Cosine"},
        "hnsw_config": {"m": 16, "ef_construct": 200},
        "optimizers_config": {"default_segment_number": 2, "memmap_threshold_kb": 20000},
    },
    "cloud_gcp": {
        "vectors": {"size": 1024, "distance": "Cosine"},
        "hnsw_config": {"m": 16, "ef_construct": 200},
        "optimizers_config": {"default_segment_number": 2, "memmap_threshold_kb": 20000},
    },
    "customer_custom": {
        "vectors": {"size": 1024, "distance": "Cosine"},
        "hnsw_config": {"m": 16, "ef_construct": 200},
        "optimizers_config": {"default_segment_number": 2, "memmap_threshold_kb": 20000},
    },
}


async def ensure_collections(config: MeshConfig) -> dict[str, bool]:
    """Create all Qdrant collections if they don't exist. Returns collection_name -> created."""
    results: dict[str, bool] = {}

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import (
            Distance,
            HnswConfig,
            OptimizersConfigDiff,
            VectorParams,
        )

        client = QdrantClient(
            host=config.qdrant.host,
            port=config.qdrant.port,
            grpc_port=config.qdrant.port if config.qdrant.use_grpc else None,
            prefer_grpc=config.qdrant.use_grpc,
        )

        existing = {c.name for c in client.get_collections().collections}

        for name, spec in COLLECTIONS.items():
            if name in existing:
                results[name] = False
                continue

            try:
                client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=spec["vectors"]["size"],
                        distance=Distance[spec["vectors"]["distance"]],
                    ),
                    hnsw_config=HnswConfig(**spec["hnsw_config"]),
                    optimizers_config=OptimizersConfigDiff(**spec["optimizers_config"]),
                )
                results[name] = True
                logger.info("Created Qdrant collection: %s", name)
            except Exception as e:
                logger.error("Failed to create collection %s: %s", name, e)
                results[name] = False

    except ImportError:
        logger.warning("qdrant_client not installed — skipping collection creation")
        for name in COLLECTIONS:
            results[name] = False
    except Exception as e:
        logger.error("Qdrant connection failed: %s", e)
        for name in COLLECTIONS:
            results[name] = False

    return results


def list_collections() -> list[dict[str, Any]]:
    """Return collection specs for catalog responses."""
    return [
        {
            "name": name,
            "vectors": spec["vectors"],
            "hnsw": spec["hnsw_config"],
            "product": name.replace("_", "."),
        }
        for name, spec in COLLECTIONS.items()
    ]
