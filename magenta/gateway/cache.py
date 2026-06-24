import hashlib
import json

from magenta.models.base import ModelRequest, ModelResponse


class SemanticCache:
    def __init__(self, enabled: bool = True, ttl_seconds: int = 3600, min_similarity: float = 0.92):
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self.min_similarity = min_similarity
        self._store: dict[str, tuple[ModelResponse, float, dict]] = {}

    async def get(self, request: ModelRequest) -> ModelResponse | None:
        if not self.enabled:
            return None

        key = self._make_key(request)
        exact = self._store.get(key)
        if exact:
            entry, ts, _ = exact
            if self._is_fresh(ts):
                return entry
            del self._store[key]

        best_sim = 0.0
        best_entry = None
        request_data = self._extract_text(request)

        for stored_key, (entry, ts, stored_data) in list(self._store.items()):
            if not self._is_fresh(ts):
                del self._store[stored_key]
                continue
            sim = self._similarity(request_data, stored_data)
            if sim > best_sim:
                best_sim = sim
                best_entry = entry

        if best_sim >= self.min_similarity:
            return best_entry
        return None

    async def set(self, request: ModelRequest, response: ModelResponse) -> None:
        if not self.enabled:
            return
        key = self._make_key(request)
        data = self._extract_text(request)
        self._store[key] = (response, self._now(), data)

    def _make_key(self, request: ModelRequest) -> str:
        content = json.dumps(
            {
                "system": request.system,
                "messages": request.messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def _extract_text(self, request: ModelRequest) -> dict:
        """Extract text content for similarity comparison."""
        texts = []
        for msg in request.messages:
            if isinstance(msg.get("content"), str):
                texts.append(msg["content"][:200])
        return {
            "system": (request.system or "")[:100],
            "texts": texts,
        }

    def _similarity(self, data_a: dict, data_b: dict) -> float:
        """Compute similarity between two request data dicts.

        Uses difflib.SequenceMatcher for fuzzy string matching on
        concatenated message content. Returns 0.0-1.0.
        """
        from difflib import SequenceMatcher

        str_a = data_a.get("system", "") + " ".join(data_a.get("texts", []))
        str_b = data_b.get("system", "") + " ".join(data_b.get("texts", []))

        if not str_a or not str_b:
            return 0.0

        return SequenceMatcher(None, str_a, str_b).ratio()

    def _is_fresh(self, ts: float) -> bool:
        return (self._now() - ts) < self.ttl_seconds

    @staticmethod
    def _now() -> float:
        import time

        return time.monotonic()
