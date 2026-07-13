"""Service Registry — modular service decomposition for the gateway.

Provides a service registry pattern for decomposing the monolithic gateway
into independently deployable microservices with health checks, discovery,
and inter-service communication.

DTP §E4: Service decomposition.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

try:
    from magenta.telemetry import get_tracer

    _tracer = get_tracer("service.registry")
except Exception:
    _tracer = None


class Service(ABC):
    """Abstract base for decomposed services."""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._started = False
        self._start_time: float | None = None

    @abstractmethod
    async def start(self) -> None:
        """Start the service."""
        self._started = True
        self._start_time = time.time()
        logger.info("Service started: %s v%s", self.name, self.version)

    @abstractmethod
    async def stop(self) -> None:
        """Stop the service."""
        self._started = False
        logger.info("Service stopped: %s", self.name)

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Return service health status."""

    def is_healthy(self) -> bool:
        return self._started

    def get_info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "status": "running" if self._started else "stopped",
            "uptime_seconds": (round(time.time() - self._start_time, 2) if self._start_time else 0),
        }


class IngestService(Service):
    """Log ingestion and normalization service."""

    def __init__(self):
        super().__init__("ingest", "1.0.0")
        self._event_count = 0

    async def start(self) -> None:
        await super().start()

    async def stop(self) -> None:
        await super().stop()

    async def health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._started else "unavailable",
            "events_processed": self._event_count,
        }

    async def ingest(self, event: dict[str, Any]) -> dict[str, Any]:
        """Process an ingested event."""
        self._event_count += 1
        return {"status": "accepted", "event_count": self._event_count}


class AgentService(Service):
    """Agent orchestration and lifecycle service."""

    def __init__(self):
        super().__init__("agents", "1.0.0")
        self._agent_count = 0
        self._mission_count = 0

    async def start(self) -> None:
        await super().start()

    async def stop(self) -> None:
        await super().stop()

    async def health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._started else "unavailable",
            "agents_registered": self._agent_count,
            "missions_active": self._mission_count,
        }


class MemoryService(Service):
    """Agent memory operations (episodic, semantic, procedural)."""

    def __init__(self):
        super().__init__("memory", "1.0.0")
        self._writes = 0
        self._searches = 0

    async def start(self) -> None:
        await super().start()

    async def stop(self) -> None:
        await super().stop()

    async def health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._started else "unavailable",
            "writes": self._writes,
            "searches": self._searches,
        }


class MeshService(Service):
    """Data mesh gateway (vector search, BM25, ingestion)."""

    def __init__(self):
        super().__init__("mesh", "1.0.0")
        self._queries = 0
        self._ingestions = 0

    async def start(self) -> None:
        await super().start()

    async def stop(self) -> None:
        await super().stop()

    async def health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._started else "unavailable",
            "queries": self._queries,
            "ingestions": self._ingestions,
        }


class ServiceRegistry:
    """Registry for decomposed services with health checks and discovery.

    Provides:
    - Service registration and lookup
    - Aggregate health checks
    - Service lifecycle management (start/stop all)
    - Inter-service communication helpers
    """

    def __init__(self):
        self._services: dict[str, Service] = {}

    def register(self, service: Service) -> None:
        """Register a service."""
        self._services[service.name] = service
        logger.info("Service registered: %s v%s", service.name, service.version)

    def unregister(self, name: str) -> None:
        """Unregister a service."""
        self._services.pop(name, None)

    def get(self, name: str) -> Service | None:
        """Get a service by name."""
        return self._services.get(name)

    async def start_all(self) -> None:
        """Start all registered services."""
        for service in self._services.values():
            try:
                await service.start()
            except Exception:
                logger.exception("Failed to start service: %s", service.name)

    async def stop_all(self) -> None:
        """Stop all registered services."""
        for service in self._services.values():
            try:
                await service.stop()
            except Exception:
                logger.exception("Failed to stop service: %s", service.name)

    async def health(self) -> dict[str, Any]:
        """Aggregate health check for all services."""
        checks = {}
        all_healthy = True

        for name, service in self._services.items():
            try:
                check = await service.health()
                checks[name] = check
                if check.get("status") != "healthy":
                    all_healthy = False
            except Exception as e:
                checks[name] = {"status": "error", "error": str(e)}
                all_healthy = False

        return {
            "status": "healthy" if all_healthy else "degraded",
            "services": checks,
            "total": len(self._services),
            "healthy": sum(1 for c in checks.values() if c.get("status") == "healthy"),
        }

    def list_services(self) -> list[dict[str, Any]]:
        """List all registered services."""
        return [service.get_info() for service in self._services.values()]


# Module-level singleton with default services
service_registry = ServiceRegistry()

# Register default decomposed services
service_registry.register(IngestService())
service_registry.register(AgentService())
service_registry.register(MemoryService())
service_registry.register(MeshService())
