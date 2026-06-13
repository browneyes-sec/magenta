import hashlib
import json
from typing import Optional

from magenta.models.base import ModelRequest, ModelResponse


class SemanticCache:
    def __init__(self, enabled: bool = True, ttl_seconds: int = 3600, min_similarity: float = 0.92):
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self.min_similarity = min_similarity
        self._store: dict[str, tuple[ModelResponse, float]] = {}

    async def get(self, request: ModelRequest) -> Optional[ModelResponse]:
        if not self.enabled:
            return None

        key = self._make_key(request)
        exact = self._store.get(key)
        if exact:
            entry, ts = exact
            if self._is_fresh(ts):
                return entry
            del self._store[key]

        best_sim = 0.0
        best_entry = None
        for stored_key, (entry, ts) in list(self._store.items()):
            if not self._is_fresh(ts):
                del self._store[stored_key]
                continue
            sim = self._similarity(request, stored_key)
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
        self._store[key] = (response, self._now())

    def _make_key(self, request: ModelRequest) -> str:
        content = json.dumps({
            "system": request.system,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def _similarity(self, request: ModelRequest, stored_key: str) -> float:
        key = self._make_key(request)
        if key == stored_key:
            return 1.0
        return 0.0

    def _is_fresh(self, ts: float) -> bool:
        return (self._now() - ts) < self.ttl_seconds

    @staticmethod
    def _now() -> float:
        import time
        return time.monotonic()
