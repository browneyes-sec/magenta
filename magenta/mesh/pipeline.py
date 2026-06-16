"""Vectorization Pipeline — chunker -> embedder (OLLAMA bge-m3) -> indexer (Qdrant)."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from magenta.mesh.config import MeshConfig

logger = logging.getLogger(__name__)


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
    """Embed text via OLLAMA API using bge-m3 model."""

    def __init__(self, config: MeshConfig):
        self.host = config.ollama.host.rstrip("/")
        self.model = config.ollama.model
        self.dimension = config.ollama.dimension
        self.batch_size = config.ollama.batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of embedding vectors."""
        import httpx

        embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.host}/api/embed",
                        json={"model": self.model, "input": batch},
                    )
                    response.raise_for_status()
                    data = response.json()
                    embeddings.extend(data.get("embeddings", []))
            except Exception as e:
                logger.error("OLLAMA embed failed for batch %d: %s", i // self.batch_size, e)
                embeddings.extend([[] for _ in batch])

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
    """Full pipeline: chunk -> embed -> index. Used by mesh_ingest and memory writes."""

    def __init__(self, config: MeshConfig | None = None):
        self.config = config or MeshConfig.from_env()
        self.chunker = SemanticChunker(
            chunk_size=self.config.chunking.default_chunk_size,
            overlap=self.config.chunking.default_overlap,
        )
        self.embedder = OllamaEmbedder(self.config)
        self.indexer = QdrantIndexer(self.config)

    async def ingest(
        self,
        collection: str,
        documents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Ingest documents: chunk, embed, index. Returns stats."""
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

            except Exception as e:
                failed += 1
                errors.append(f"Document {doc_id}: {e}")

        return {"ingested": ingested, "failed": failed, "errors": errors}

    async def search(
        self,
        collection: str,
        query: str,
        filters: dict | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search: embed query, search Qdrant, return ranked results."""
        query_embedding = await self.embedder.embed_single(query)
        if not query_embedding:
            return []
        return await self.indexer.search(collection, query_embedding, filters, top_k)
