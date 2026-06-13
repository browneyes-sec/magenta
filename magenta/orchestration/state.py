"""State management for missions and agents."""

from typing import Any, Optional
from datetime import datetime, timedelta
import json


class InMemoryStateStore:
    """Simple in-memory state store (for dev/testing; Redis for prod)."""

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._ttl: dict[str, datetime] = {}

    async def set(self, key: str, value: Any, ttl_seconds: int = 0) -> None:
        self._data[key] = value
        if ttl_seconds > 0:
            self._ttl[key] = datetime.utcnow() + timedelta(seconds=ttl_seconds)

    async def get(self, key: str) -> Optional[Any]:
        if key in self._ttl:
            if datetime.utcnow() > self._ttl[key]:
                await self.delete(key)
                return None
        return self._data.get(key)

    async def delete(self, key: str) -> bool:
        self._ttl.pop(key, None)
        return self._data.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        val = await self.get(key)
        return val is not None

    async def keys(self, pattern: str = "") -> list[str]:
        if pattern:
            return [k for k in self._data if pattern in k]
        return list(self._data.keys())

    async def clear(self) -> None:
        self._data.clear()
        self._ttl.clear()


state_store = InMemoryStateStore()
