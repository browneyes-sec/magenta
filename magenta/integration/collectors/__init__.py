"""Log collector base classes and registry."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CollectorConfig:
    name: str
    source_type: str  # windows_event | linux_syslog | cloud.* | customer.*
    poll_interval_seconds: int = 60
    batch_size: int = 100
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)


class BaseCollector(ABC):
    """Abstract base for all log collectors."""

    def __init__(self, config: CollectorConfig):
        self.config = config
        self._running = False

    @abstractmethod
    async def collect(self) -> list[dict]:
        """Collect log events — returns list of raw event dicts."""
        ...

    @abstractmethod
    async def health(self) -> dict:
        """Health check specific to this collector."""
        ...

    async def start(self) -> None:
        self._running = True
        logger.info("Collector started: %s", self.config.name)

    async def stop(self) -> None:
        self._running = False
        logger.info("Collector stopped: %s", self.config.name)

    @property
    def is_running(self) -> bool:
        return self._running
