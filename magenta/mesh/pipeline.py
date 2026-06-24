"""Vectorization Pipeline — chunker -> embedder (OLLAMA bge-m3) -> indexer (Qdrant)."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from magenta.mesh.bm25 import TantivyBM25Sidecar
from magenta.mesh.config import MeshConfig

logger = logging.getLogger(__name__)

try:
    from magenta.mesh.lineage import lineage_tracker
except Exception:
    lineage_tracker = None


# ── Chunker ──────────────────────────────────────────────────────────────

class SemanticChunker:
    """Split text into semantic chunks by sentence/paragraph boundaries."""

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 64,
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        chunks: list[str] = []
        current = ""
        current_len = 0

        for sentence in sentences:
            sentence_tokens = len(sentence.split())
            if current_len + sentence_tokens > self.chunk_size and current:
                chunks.append(current.strip())
                overlap_text = " ".join(current.split()[-self.overlap:]) if self.overlap else ""
                current = f"{overlap_text} {sentence}".strip()
                current_len = len(current.split())
            else:
                current = f"{current} {sentence}".strip() if current else sentence
                current_len += sentence_tokens

        if current.strip():
            chunks.append(current.strip())

        return chunks if chunks else [text[: self.chunk_size]]


# ── Embedder ──────────────────────────────────────────────────────────────

class OllamaEmbedder:
    """Embed text via OLLAMA API using nomic-embed-text model.

    Includes a 24h TTL cache to avoid redundant embedding calls.
    """

    def __init__(self, config: MeshConfig):
        self.host = config.ollama.host.rstrip("/")
        self.model = config.ollama.model
        self.dimension = config.ollama.dimension
        self.batch_size = config.ollama.batch_size
        self._cache: dict[str, tuple[list[float], float]] = {}
        self._cache_ttl = 86400  # 24 hours

    def _cache_key(self, text: str) -> str:
        import hashlib
        return hashlib.sha256(f"{self.model}:{text}".encode()).hexdigest()[:16]

    def _is_cache_fresh(self, ts: float) -> bool:
        import time
        return (time.monotonic() - ts) < self._cache_ttl

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of embedding vectors."""
        import time

        import httpx

        embeddings: list[list[float]] = []
        uncached_texts: list[str] = []
        uncached_indices: list[int] = []

        # Check cache first
        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._cache:
                vec, ts = self._cache[key]
                if self._is_cache_fresh(ts):
                    embeddings.append(vec)
                    continue
            embeddings.append([])  # placeholder
            uncached_texts.append(text)
            uncached_indices.append(i)

        # Embed uncached texts in batches
        for i in range(0, len(uncached_texts), self.batch_size):
            batch = uncached_texts[i : i + self.batch_size]
            batch_indices = uncached_indices[i : i + self.batch_size]
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.host}/api/embed",
                        json={"model": self.model, "input": batch},
                    )
                    response.raise_for_status()
                    data = response.json()
                    batch_embeddings = data.get("embeddings", [])
                    for j, (idx, emb) in enumerate(zip(batch_indices, batch_embeddings)):
                        embeddings[idx] = emb
                        self._cache[self._cache_key(batch[j])] = (emb, time.monotonic())
            except Exception as e:
                logger.error("OLLAMA embed failed for batch %d: %s", i // self.batch_size, e)

        return embeddings

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text."""
        results = await self.embed([text])
        return results[0] if results else []


# ── Indexer ──────────────────────────────────────────────────────────────

class QdrantIndexer:
    """Upsert vectors and payloads into Qdrant collections."""

    def __init__(self, config: MeshConfig):
        self.config = config
        self._client = None

    def _get_client(self):
        if self._client is None:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(
                host=self.config.qdrant.host,
                port=self.config.qdrant.port,
                grpc_port=self.config.qdrant.port if self.config.qdrant.use_grpc else None,
                prefer_grpc=self.config.qdrant.use_grpc,
            )
        return self._client

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> int:
        """Upsert vectors with payloads. Returns count of successful upserts."""
        try:
            from qdrant_client.models import PointStruct

            points = [
                PointStruct(id=ids[i], vector=vectors[i], payload=payloads[i])
                for i in range(len(ids))
            ]

            client = self._get_client()
            client.upsert(collection_name=collection, points=points)
            return len(points)

        except Exception as e:
            logger.error("Qdrant upsert failed for collection %s: %s", collection, e)
            return 0

    async def search(
        self,
        collection: str,
        vector: list[float],
        filters: dict | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search a Qdrant collection with optional payload filters."""
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            query_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    if isinstance(value, list):
                        for v in value:
                            conditions.append(
                                FieldCondition(key=key, match=MatchValue(value=v))
                            )
                    else:
                        conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
                if conditions:
                    query_filter = Filter(must=conditions)

            client = self._get_client()
            results = client.search(
                collection_name=collection,
                query_vector=vector,
                query_filter=query_filter,
                limit=top_k,
            )

            return [
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "payload": hit.payload or {},
                }
                for hit in results
            ]

        except Exception as e:
            logger.error("Qdrant search failed for collection %s: %s", collection, e)
            return []


# ── Pipeline ──────────────────────────────────────────────────────────────

class VectorizationPipeline:
    """Full pipeline: chunk -> embed -> index. Used by mesh_ingest and memory writes.

    Supports hybrid search via Reciprocal Rank Fusion (RRF) combining
    dense vector search (Qdrant) and sparse lexical search (BM25).
    """

    def __init__(self, config: MeshConfig | None = None):
        self.config = config or MeshConfig.from_env()
        self.chunker = SemanticChunker(
            chunk_size=self.config.chunking.default_chunk_size,
            overlap=self.config.chunking.default_overlap,
        )
        self.embedder = OllamaEmbedder(self.config)
        self.indexer = QdrantIndexer(self.config)
        self._bm25_sidecars: dict[str, TantivyBM25Sidecar] = {}
        self._bm25_rebuilt: set[str] = set()

    async def initialize(self) -> None:
        """Rebuild BM25 indexes from Qdrant for all known collections.

        Called on startup to restore sparse search after restart.
        """
        for collection in ("mem_episodic", "mem_semantic", "mem_procedural"):
            if collection not in self._bm25_rebuilt:
                bm25 = self._get_bm25(collection)
                await bm25.rebuild_from_qdrant(self.config)
                self._bm25_rebuilt.add(collection)
        logger.info("VectorizationPipeline initialized with BM25 rebuilt for %d collections", len(self._bm25_rebuilt))

    def _get_bm25(self, collection: str) -> TantivyBM25Sidecar:
        if collection not in self._bm25_sidecars:
            self._bm25_sidecars[collection] = TantivyBM25Sidecar(collection=collection)
        return self._bm25_sidecars[collection]

    async def ingest(
        self,
        collection: str,
        documents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Ingest documents: chunk, embed, index. Returns stats."""
        run_id = None
        if lineage_tracker:
            run_id = lineage_tracker.start_run(
                job_name=f"pipeline.ingest.{collection}",
                inputs=[{"name": f"documents:{len(documents)}", "namespace": "magenta.ingest"}],
            )

        ingested = 0
        failed = 0
        errors: list[str] = []

        for doc in documents:
            doc_id = doc.get("id", str(uuid4()))
            text = doc.get("text", "")
            metadata = doc.get("metadata", {})

            if not text:
                failed += 1
                errors.append(f"Document {doc_id}: empty text")
                continue

            try:
                chunks = self.chunker.chunk(text)
                embeddings = await self.embedder.embed(chunks)

                ids = []
                vectors = []
                payloads = []

                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    if not embedding:
                        failed += 1
                        errors.append(f"Document {doc_id} chunk {i}: empty embedding")
                        continue

                    point_id = hashlib.sha256(
                        f"{doc_id}:{i}:{chunk[:100]}".encode()
                    ).hexdigest()[:16]

                    ids.append(point_id)
                    vectors.append(embedding)
                    payloads.append({
                        **metadata,
                        "doc_id": doc_id,
                        "chunk_index": i,
                        "chunk_total": len(chunks),
                        "text": chunk,
                        "timestamp": datetime.now(UTC).isoformat(),
                    })

                if vectors:
                    result = await self.indexer.upsert(collection, ids, vectors, payloads)
                    ingested += result

                    bm25 = self._get_bm25(collection)
                    for chunk, payload in zip(
                        [doc.get("text", "")] if len(chunks) == 1 else chunks,
                        payloads,
                    ):
                        bm25.add_document(
                            doc_id=payload.get("doc_id", ""),
                            text=chunk,
                            metadata=payload,
                        )
                    bm25.commit()

            except Exception as e:
                failed += 1
                errors.append(f"Document {doc_id}: {e}")

        if lineage_tracker and run_id:
            lineage_tracker.complete_run(
                run_id,
                outputs=[{"name": f"qdrant:{collection}", "namespace": "magenta.storage"}],
                facets={"magenta": {"ingested": ingested, "failed": failed}},
            )

        return {"ingested": ingested, "failed": failed, "errors": errors}

    async def search(
        self,
        collection: str,
        query: str,
        filters: dict | None = None,
        top_k: int = 10,
        hybrid: bool = True,
    ) -> list[dict[str, Any]]:
        """Search: embed query, search Qdrant, return ranked results.

        When hybrid=True, combines dense vector search with sparse BM25
        search via Reciprocal Rank Fusion (RRF).

        RRF score = sum(1 / (k + rank_i)) for each ranking i,
        where k=60 is the RRF constant (standard value).
        """
        query_embedding = await self.embedder.embed_single(query)
        if not query_embedding:
            return []

        vector_results = await self.indexer.search(collection, query_embedding, filters, top_k)

        if not hybrid:
            return vector_results

        bm25 = self._get_bm25(collection)
        bm25_results = bm25.search(query, top_k=top_k)

        return self._rrf_fusion(vector_results, bm25_results, top_k)

    @staticmethod
    def _rrf_fusion(
        vector_results: list[dict],
        bm25_results: list[dict],
        top_k: int,
        k: int = 60,
    ) -> list[dict[str, Any]]:
        """Reciprocal Rank Fusion of vector and BM25 results.

        Args:
            vector_results: Dense vector search results.
            bm25_results: Sparse BM25 search results.
            top_k: Number of results to return.
            k: RRF constant (default 60, standard in literature).
        """
        doc_scores: dict[str, float] = {}
        doc_data: dict[str, dict] = {}

        for rank, result in enumerate(vector_results):
            doc_id = result.get("id", "")
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
            doc_data[doc_id] = result

        for rank, result in enumerate(bm25_results):
            doc_id = result.get("id", "")
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
            if doc_id not in doc_data:
                doc_data[doc_id] = result

        sorted_ids = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)[:top_k]

        return [
            {
                **doc_data[doc_id],
                "rrf_score": doc_scores[doc_id],
            }
            for doc_id in sorted_ids
        ]
