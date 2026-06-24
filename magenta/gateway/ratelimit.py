import asyncio
import time


class TokenBucket:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._buckets: dict[str, dict] = {}

    async def consume(self, provider: str, tokens: int = 1) -> bool:
        now = time.monotonic()
        bucket = self._buckets.setdefault(provider, {
            "tokens": 10,
            "max_tokens": 10,
            "refill_rate": 1.0,
            "last_refill": now,
        })
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(
            bucket["max_tokens"],
            bucket["tokens"] + elapsed * bucket["refill_rate"],
        )
        bucket["last_refill"] = now

        if bucket["tokens"] >= tokens:
            bucket["tokens"] -= tokens
            return True
        return False

    async def wait(self, provider: str, tokens: int = 1) -> None:
        while not await self.consume(provider, tokens):
            await asyncio.sleep(0.1)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state: dict[str, dict] = {}

    async def is_open(self, provider: str) -> bool:
        state = self._state.get(provider)
        if not state:
            return False
        if state["failures"] >= self.failure_threshold:
            if time.monotonic() - state["last_failure"] > self.recovery_timeout:
                state["failures"] = 0
                state["last_failure"] = 0
                return False
            return True
        return False

    async def record_failure(self, provider: str) -> None:
        state = self._state.setdefault(provider, {"failures": 0, "last_failure": 0})
        state["failures"] += 1
        state["last_failure"] = time.monotonic()

    async def record_success(self, provider: str) -> None:
        state = self._state.get(provider)
        if state:
            state["failures"] = 0
