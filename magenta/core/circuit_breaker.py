"""Circuit breaker pattern for integration layer resilience.

Provides a state machine (Closed → Open → Half-Open) that prevents
cascade failures when external services are unavailable.

Usage:
    breaker = CircuitBreaker(name="soar", failure_threshold=5, reset_timeout=30)
    result = await breaker.call(some_async_fn, arg1, arg2)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from magenta.exceptions import IntegrationError

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker with Closed/Open/Half-Open states.

    Thread-safe for async use. Each instance tracks its own failure count
    and state transitions.

    Attributes:
        name: Human-readable name for logging.
        failure_threshold: Consecutive failures before opening.
        reset_timeout: Seconds before transitioning from Open to Half-Open.
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state: str = "CLOSED"
        self._failure_count: int = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls: int = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        """Get current circuit state with automatic Half-Open transition."""
        if self._state == "OPEN" and self._last_failure_time:
            elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
            if elapsed >= self.reset_timeout:
                self._state = "HALF_OPEN"
                self._half_open_calls = 0
                logger.info(
                    "CircuitBreaker[%s]: OPEN → HALF_OPEN (reset_timeout=%.1fs elapsed)",
                    self.name,
                    elapsed,
                )
        return self._state

    async def call(self, fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        """
        Execute an async function through the circuit breaker.

        Args:
            fn: Async function to execute.
            *args: Positional arguments passed to fn.
            **kwargs: Keyword arguments passed to fn.

        Returns:
            The result of the function call.

        Raises:
            IntegrationError: If the circuit is OPEN.
            Original exception: If the function call fails.
        """
        async with self._lock:
            current_state = self.state

            if current_state == "OPEN":
                raise IntegrationError(
                    f"CircuitBreaker[{self.name}]: OPEN — "
                    f"calls rejected until reset timeout ({self.reset_timeout}s)"
                )

            if current_state == "HALF_OPEN":
                if self._half_open_calls >= self.half_open_max_calls:
                    raise IntegrationError(
                        f"CircuitBreaker[{self.name}]: HALF_OPEN — "
                        f"probe call quota exhausted ({self._half_open_calls}/{self.half_open_max_calls})"
                    )
                self._half_open_calls += 1

        # Execute outside the lock to avoid holding it during the call
        try:
            result = await fn(*args, **kwargs)
        except Exception:
            await self._record_failure()
            raise

        await self._record_success()
        return result

    async def _record_success(self) -> None:
        async with self._lock:
            if self._state == "HALF_OPEN":
                logger.info(
                    "CircuitBreaker[%s]: HALF_OPEN → CLOSED (probe succeeded)",
                    self.name,
                )
            self._state = "CLOSED"
            self._failure_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None

    async def _record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()

            if self._state == "HALF_OPEN":
                self._state = "OPEN"
                logger.warning(
                    "CircuitBreaker[%s]: HALF_OPEN → OPEN (probe failed)",
                    self.name,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = "OPEN"
                logger.warning(
                    "CircuitBreaker[%s]: CLOSED → OPEN (%d consecutive failures, threshold=%d)",
                    self.name,
                    self._failure_count,
                    self.failure_threshold,
                )

    async def reset(self) -> None:
        """Force reset the circuit breaker to Closed state."""
        async with self._lock:
            self._state = "CLOSED"
            self._failure_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
            logger.info("CircuitBreaker[%s]: FORCE RESET → CLOSED", self.name)

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics for monitoring."""
        return {
            "name": self.name,
            "state": self._state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self._last_failure_time.isoformat()
            if self._last_failure_time
            else None,
            "reset_timeout": self.reset_timeout,
        }
