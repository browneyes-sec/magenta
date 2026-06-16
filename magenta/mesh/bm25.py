"""Tantivy BM25 Sidecar — sparse lexical search for hybrid retrieval.

Provides BM25 keyword search alongside Qdrant vector search.
Used by the VectorizationPipeline for reciprocal rank fusion (RRF).

Requires: tantivy (Python bindings to Tantivy Rust library)
Fallback: Simple in-memory TF-IDF if tantivy is not installed.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)

try:
    import tantivy
    from tantivy import STORED, TEXT, SchemaBuilder
    HAS_TANTIVY = True
except ImportError:
    HAS_TANTIVY = False
    logger.warning("tantivy not installed — using fallback TF-IDF searcher")


class _FallbackBM25Searcher:
    """In-memory TF-IDF fallback when tantivy is not available.

    Good enough for development and small collections (<100k docs).
    For production, install tantivy for proper BM25 scoring.
    """

    def __init__(self):
        self._documents: dict[str, dict[str, Any]] = {}
        self._index: dict[str, Counter] = {}
        self._doc_freq: Counter = Counter()
        self._total_docs = 0

    def add_document(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        tokens = self._tokenize(text)
        self._documents[doc_id] = {"text": text, "metadata": metadata or {}}
        self._index[doc_id] = Counter(tokens)
        for token in set(tokens):
            self._doc_freq[token] += 1
        self._total_docs += 1

    def remove_document(self, doc_id: str) -> None:
        if doc_id in self._documents:
            tokens = self._tokenize(self._documents[doc_id]["text"])
            self._index.pop(doc_id, None)
            self._documents.pop(doc_id, None)
            for token in set(tokens):
                self._doc_freq[token] = max(0, self._doc_freq[token] - 1)
            self._total_docs = max(0, self._total_docs - 1)

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores: dict[str, float] = {}
        for doc_id, term_freqs in self._index.items():
            score = 0.0
            for token in query_tokens:
                if token in term_freqs:
                    tf = term_freqs[token]
                    df = self._doc_freq.get(token, 0)
                    idf = (self._total_docs - df + 0.5) / (df + 0.5) if self._total_docs > 0 else 0
                    score += tf * idf
            if score > 0:
                scores[doc_id] = score

        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return [
            {
                "id": doc_id,
                "score": score,
                "text": self._documents[doc_id]["text"],
                "metadata": self._documents[doc_id]["metadata"],
            }
            for doc_id, score in sorted_docs
        ]

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        tokens = text.split()
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                       "have", "has", "had", "do", "does", "did", "will", "would", "could",
                       "should", "may", "might", "shall", "can", "need", "dare", "ought",
                       "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
                       "as", "into", "through", "during", "before", "after", "above", "below",
                       "between", "out", "off", "over", "under", "again", "further", "then",
                       "once", "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
                       "neither", "each", "every", "all", "any", "few", "more", "most", "other",
                       "some", "such", "no", "only", "own", "same", "than", "too", "very"}
        return [t for t in tokens if t not in stop_words and len(t) > 1]

    def count(self) -> int:
        return self._total_docs


class TantivyBM25Sidecar:
    """BM25 lexical search sidecar for hybrid retrieval.

    Provides sparse keyword search that complements dense vector search.
    Results are combined via reciprocal rank fusion (RRF) in the pipeline.

    Args:
        collection: Collection name this sidecar serves.
        use_tantivy: Force Tantivy usage (default: auto-detect).
    """

    def __init__(self, collection: str = "", use_tantivy: bool | None = None):
        self.collection = collection
        self._use_tantivy = use_tantivy if use_tantivy is not None else HAS_TANTIVY

        if self._use_tantivy and HAS_TANTIVY:
            self._schema = SchemaBuilder().add_text_field("text", STORED | TEXT).build()
            self._index = tantivy.Index(self._schema)
            self._writer = self._index.writer()
            self._searcher = self._index.searcher()
            self._doc_count = 0
            logger.info("Tantivy BM25 sidecar initialized for collection=%s", collection)
        else:
            self._fallback = _FallbackBM25Searcher()
            logger.info("Fallback TF-IDF sidecar initialized for collection=%s", collection)

    def add_document(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """Add a document to the BM25 index."""
        if self._use_tantivy and HAS_TANTIVY:
            doc = tantivy.Document()
            doc.add_text("text", text)
            self._writer.add_document(doc)
            self._doc_count += 1
            if self._doc_count % 100 == 0:
                self._writer.commit()
        else:
            self._fallback.add_document(doc_id, text, metadata)

    def remove_document(self, doc_id: str) -> None:
        """Remove a document from the BM25 index."""
        if not (self._use_tantivy and HAS_TANTIVY):
            self._fallback.remove_document(doc_id)

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """BM25 search returning [{id, score, text, metadata}]."""
        if self._use_tantivy and HAS_TANTIVY:
            return self._search_tantivy(query, top_k)
        return self._fallback.search(query, top_k)

    def _search_tantivy(self, query: str, top_k: int) -> list[dict[str, Any]]:
        try:
            query_parser = self._index.parse_query(query)
            results = self._searcher.search(query_parser, limit=top_k)

            output = []
            for hit in results.hits:
                doc = self._searcher.doc(hit.doc_address)
                output.append({
                    "id": str(hit.doc_id),
                    "score": hit.score,
                    "text": doc.get_first("text") or "",
                    "metadata": {},
                })
            return output
        except Exception:
            logger.exception("Tantivy search failed for collection=%s", self.collection)
            return []

    def commit(self) -> None:
        """Commit pending changes to the index."""
        if self._use_tantivy and HAS_TANTIVY:
            self._writer.commit()

    def count(self) -> int:
        """Return the number of indexed documents."""
        if self._use_tantivy and HAS_TANTIVY:
            return self._doc_count
        return self._fallback.count()
