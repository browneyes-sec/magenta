"""CDC Connector Framework — Debezium-style change data capture.

Provides pluggable CDC connectors for SQL and NoSQL databases,
emitting change events to the mesh pipeline for vectorization.

DTP §E3: CDC Connectors (Debezium for SQL, Change Streams for NoSQL).
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

try:
    from magenta.telemetry import get_tracer
    _tracer = get_tracer("cdc.connector")
except Exception:
    _tracer = None


class ChangeEvent:
    """A single change event from a CDC connector."""

    def __init__(
        self,
        source_type: str,
        database: str,
        collection: str,
        operation: str,
        document_id: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        timestamp: str = "",
    ):
        self.event_id = str(uuid4())
        self.source_type = source_type
        self.database = database
        self.collection = collection
        self.operation = operation  # c=create, u=update, d=delete, r=read
        self.document_id = document_id
        self.before = before or {}
        self.after = after or {}
        self.timestamp = timestamp or datetime.now(UTC).isoformat()
        self.captured_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_type": self.source_type,
            "database": self.database,
            "collection": self.collection,
            "operation": self.operation,
            "document_id": self.document_id,
            "before": self.before,
            "after": self.after,
            "timestamp": self.timestamp,
            "captured_at": self.captured_at,
            "schema_version": "1.0",
            "event_type": "cdc.change",
        }


class CDCConnector(ABC):
    """Abstract base for CDC connectors."""

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        self.name = name
        self.config = config or {}
        self._running = False
        self._stats = {
            "events_captured": 0,
            "events_failed": 0,
            "started_at": None,
            "last_event_at": None,
        }

    @abstractmethod
    async def start(self) -> None:
        """Start the CDC connector."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the CDC connector."""

    @abstractmethod
    async def capture_changes(self) -> list[ChangeEvent]:
        """Capture a batch of changes. Returns list of change events."""

    def get_stats(self) -> dict[str, Any]:
        return {**self._stats}


class SQLCDCConnector(CDCConnector):
    """CDC connector for SQL databases (SQL Server, PostgreSQL, MySQL).

    Uses polling-based change capture (compatible with Debezium output format).
    For production, use Debezium Server with Kafka Connect.
    """

    def __init__(
        self,
        name: str,
        connection_string: str = "",
        poll_interval_seconds: int = 5,
        tracked_tables: list[str] | None = None,
        **kwargs: Any,
    ):
        super().__init__(name, kwargs)
        self.connection_string = connection_string
        self.poll_interval = poll_interval_seconds
        self.tracked_tables = tracked_tables or []
        self._last_watermark: dict[str, Any] = {}

    async def start(self) -> None:
        self._running = True
        self._stats["started_at"] = time.time()
        logger.info("SQL CDC connector started: name=%s tables=%s", self.name, self.tracked_tables)

    async def stop(self) -> None:
        self._running = False
        logger.info("SQL CDC connector stopped: name=%s", self.name)

    async def capture_changes(self) -> list[ChangeEvent]:
        """Poll for changes using watermark-based tracking.

        In production, this would use Debezium's MySQL/PostgreSQL connector
        with Kafka Connect. This implementation provides the interface and
        a polling fallback for development.
        """
        if not self._running:
            return []

        events: list[ChangeEvent] = []

        try:
            for table in self.tracked_tables:
                changes = await self._poll_table(table)
                events.extend(changes)
        except Exception:
            logger.exception("Failed to capture SQL CDC changes")
            self._stats["events_failed"] += 1

        self._stats["events_captured"] += len(events)
        if events:
            self._stats["last_event_at"] = time.time()

        return events

    async def _poll_table(self, table: str) -> list[ChangeEvent]:
        """Poll a single table for changes. Override in production."""
        return []


class NoSQLCDCConnector(CDCConnector):
    """CDC connector for NoSQL databases (MongoDB Change Streams).

    Uses MongoDB Change Streams for real-time change capture.
    """

    def __init__(
        self,
        name: str,
        connection_string: str = "",
        database: str = "",
        watched_collections: list[str] | None = None,
        **kwargs: Any,
    ):
        super().__init__(name, kwargs)
        self.connection_string = connection_string
        self.database = database
        self.watched_collections = watched_collections or []
        self._resume_tokens: dict[str, Any] = {}

    async def start(self) -> None:
        self._running = True
        self._stats["started_at"] = time.time()
        logger.info(
            "NoSQL CDC connector started: name=%s db=%s collections=%s",
            self.name, self.database, self.watched_collections,
        )

    async def stop(self) -> None:
        self._running = False
        logger.info("NoSQL CDC connector stopped: name=%s", self.name)

    async def capture_changes(self) -> list[ChangeEvent]:
        """Listen to MongoDB Change Streams for real-time changes."""
        if not self._running:
            return []

        events: list[ChangeEvent] = []

        try:
            for collection in self.watched_collections:
                changes = await self._watch_collection(collection)
                events.extend(changes)
        except Exception:
            logger.exception("Failed to capture NoSQL CDC changes")
            self._stats["events_failed"] += 1

        self._stats["events_captured"] += len(events)
        if events:
            self._stats["last_event_at"] = time.time()

        return events

    async def _watch_collection(self, collection: str) -> list[ChangeEvent]:
        """Watch a single collection. Override in production."""
        return []


class EventHubCDCConnector(CDCConnector):
    """CDC connector that consumes from Azure Event Hubs.

    Bridges external Event Hub topics into the CDC event format
    for uniform processing by the mesh pipeline.
    """

    def __init__(
        self,
        name: str,
        eventhub_client: Any = None,
        topic: str = "",
        consumer_group: str = "$Default",
        **kwargs: Any,
    ):
        super().__init__(name, kwargs)
        self._client = eventhub_client
        self.topic = topic
        self.consumer_group = consumer_group
        self._pending_events: list[ChangeEvent] = []

    async def start(self) -> None:
        self._running = True
        self._stats["started_at"] = time.time()

        if self._client:
            await self._client.start_consumer(
                topic=self.topic,
                handler=self._handle_event,
                consumer_group=self.consumer_group,
            )

        logger.info("EventHub CDC connector started: topic=%s", self.topic)

    async def stop(self) -> None:
        self._running = False
        if self._client:
            await self._client.stop_consumer(self.topic)
        logger.info("EventHub CDC connector stopped: topic=%s", self.topic)

    async def _handle_event(self, message: dict) -> None:
        """Convert Event Hub message to CDC ChangeEvent."""
        event = ChangeEvent(
            source_type="eventhub",
            database="",
            collection=self.topic,
            operation="c",
            document_id=message.get("event_id", str(uuid4())),
            after=message,
            timestamp=message.get("timestamp", datetime.now(UTC).isoformat()),
        )
        self._pending_events.append(event)

    async def capture_changes(self) -> list[ChangeEvent]:
        """Return buffered events from Event Hub consumer."""
        events = list(self._pending_events)
        self._pending_events.clear()
        self._stats["events_captured"] += len(events)
        if events:
            self._stats["last_event_at"] = time.time()
        return events


class CDCManager:
    """Manages multiple CDC connectors and routes change events."""

    def __init__(self):
        self._connectors: dict[str, CDCConnector] = {}
        self._handlers: dict[str, Any] = {}

    def register(self, connector: CDCConnector) -> None:
        self._connectors[connector.name] = connector
        logger.info("CDC connector registered: %s", connector.name)

    def unregister(self, name: str) -> None:
        self._connectors.pop(name, None)

    async def start_all(self) -> None:
        for connector in self._connectors.values():
            try:
                await connector.start()
            except Exception:
                logger.exception("Failed to start CDC connector: %s", connector.name)

    async def stop_all(self) -> None:
        for connector in self._connectors.values():
            try:
                await connector.stop()
            except Exception:
                logger.exception("Failed to stop CDC connector: %s", connector.name)

    async def poll_all(self) -> list[ChangeEvent]:
        """Poll all connectors for changes."""
        all_events: list[ChangeEvent] = []
        for connector in self._connectors.values():
            try:
                events = await connector.capture_changes()
                all_events.extend(events)
            except Exception:
                logger.exception("Failed to poll CDC connector: %s", connector.name)
        return all_events

    def get_stats(self) -> dict[str, Any]:
        return {
            name: connector.get_stats()
            for name, connector in self._connectors.items()
        }


# Module-level singleton
cdc_manager = CDCManager()
