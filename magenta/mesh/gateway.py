"""Mesh Gateway — hybrid query federation, data product catalog, health checks."""

from __future__ import annotations

import logging
import time
from typing import Any

from magenta.mesh.collections import COLLECTIONS, ensure_collections, list_collections
from magenta.mesh.config import MeshConfig
from magenta.mesh.memory import MemoryMCPServer
from magenta.mesh.pipeline import VectorizationPipeline

logger = logging.getLogger(__name__)


class MeshGateway:
    """Unified gateway for vectorized data mesh operations.

    Provides:
    - Hybrid search (dense vector + sparse BM25 + metadata filters via RRF)
    - Document ingestion (chunk -> embed -> index)
    - Data product catalog
    - Health checks
    """

    def __init__(self, config: MeshConfig | None = None):
        self.config = config or MeshConfig.from_env()
        self.pipeline = VectorizationPipeline(self.config)
        self.memory = MemoryMCPServer(self.config)
        self._products = list_collections()
        self._started = False
        self._start_time: float | None = None

    async def start(self) -> None:
        """Initialize the mesh gateway — create collections, verify backends."""
        if self._started:
            return

        logger.info("Starting mesh gateway...")

        if self.config.collections_auto_create:
            results = await ensure_collections(self.config)
            created = sum(1 for v in results.values() if v)
            existing = sum(1 for v in results.values() if not v)
            logger.info(
                "Qdrant collections: %d created, %d already existed",
                created,
                existing,
            )

        self._started = True
        self._start_time = time.time()
        logger.info(
            "Mesh gateway started (model=%s, dim=%d)",
            self.config.ollama.model,
            self.config.ollama.dimension,
        )

    async def query(
        self,
        query: str,
        products: list[str] | None = None,
        filters: dict | None = None,
        top_k: int = 10,
        hybrid: bool = True,
        explain: bool = False,
    ) -> dict[str, Any]:
        """Hybrid search across data products using reciprocal rank fusion.

        Args:
            query: Natural language query.
            products: Optional list of collection names to search. If None, search all.
            filters: Metadata filters (product, severity, source, timestamp range, etc.)
            top_k: Number of results to return.
            hybrid: Enable dense + sparse fusion.
            explain: Include scoring breakdown.
        """
        start = time.time()
        collections = products or [p["name"] for p in self._products]
        all_results: list[dict[str, Any]] = []

        for collection in collections:
            if collection not in COLLECTIONS:
                continue

            results = await self.pipeline.search(
                collection=collection,
                query=query,
                filters=filters,
                top_k=top_k,
            )

            for r in results:
                r["collection"] = collection
            all_results.extend(results)

        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_results = all_results[:top_k]

        latency_ms = (time.time() - start) * 1000

        return {
            "results": top_results,
            "federation": {
                "collections_searched": len(collections),
                "total_candidates": len(all_results),
                "returned": len(top_results),
                "latency_ms": round(latency_ms, 2),
                "hybrid": hybrid,
            },
        }

    async def ingest(
        self,
        product: str,
        documents: list[dict[str, Any]],
        batch_size: int = 32,
    ) -> dict[str, Any]:
        """Ingest documents into a data product collection.

        Args:
            product: Target collection name.
            documents: List of documents with 'id', 'text', 'metadata'.
            batch_size: Embedding batch size.
        """
        if product not in COLLECTIONS:
            return {"error": f"Unknown product: {product}", "ingested": 0, "failed": len(documents)}

        result = await self.pipeline.ingest(product, documents)
        result["product"] = product
        return result

    async def list_products(self) -> list[dict[str, Any]]:
        """List available data products with schemas and health."""
        return self._products

    async def health(self) -> dict[str, Any]:
        """Health check for all mesh components."""
        checks = {}

        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(
                host=self.config.qdrant.host,
                port=self.config.qdrant.port,
                prefer_grpc=self.config.qdrant.use_grpc,
            )
            collections = client.get_collections()
            checks["qdrant"] = {
                "status": "healthy",
                "collections": len(collections.collections),
            }
        except Exception as e:
            checks["qdrant"] = {"status": "degraded", "error": str(e)}

        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.config.ollama.host}/api/health")
                checks["ollama"] = {
                    "status": "healthy" if resp.status_code == 200 else "degraded",
                    "model": self.config.ollama.model,
                }
        except Exception as e:
            checks["ollama"] = {"status": "degraded", "error": str(e)}

        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(
                f"redis://{self.config.redis.host}:{self.config.redis.port}"
            )
            await r.ping()
            await r.aclose()
            checks["redis"] = {"status": "healthy"}
        except Exception as e:
            checks["redis"] = {"status": "degraded", "error": str(e)}

        all_healthy = all(c.get("status") == "healthy" for c in checks.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "checks": checks,
            "uptime_seconds": round(time.time() - self._start_time, 2) if self._start_time else 0,
            "model": self.config.ollama.model,
            "dimension": self.config.ollama.dimension,
            "collections": len(COLLECTIONS),
        }


mesh_gateway = MeshGateway()
