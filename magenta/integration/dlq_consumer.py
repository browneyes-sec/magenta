"""Dead-Letter Queue (DLQ) Consumer — processes failed Event Hub messages.

Consumes messages from the dead-letter topic, logs failure details,
and optionally archives to Elasticsearch for offline analysis.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from magenta.integration.eventhub import EventHubClient

logger = logging.getLogger(__name__)


class DLQConsumer:
    """Consumes messages from Event Hubs dead-letter topics.

    When a message fails processing (exhausted retries, schema validation
    error, etc.), it is routed to the dead-letter topic. This consumer
    picks up those messages, logs structured failure records, and
    optionally archives them to Elasticsearch for post-mortem analysis.

    Architecture (DTP §2):
    - DLQ topic: ``{source_topic}-dead-letter``
    - Consumer group: ``dlq-processor``
    - Retention: 7 days (Event Hub level)
    - Archive: Elasticsearch index ``magenta-dlq-{yyyy.MM.dd}``
    """

    def __init__(
        self,
        client: EventHubClient,
        *,
        source_topics: list[str] | None = None,
        elasticsearch_client: Any | None = None,
        handler: Callable[[dict], Awaitable[None]] | None = None,
    ):
        self._client = client
        self._source_topics = source_topics or ["raw-alerts", "enriched-alerts", "actions"]
        self._es_client = elasticsearch_client
        self._custom_handler = handler
        self._stats = {
            "consumed": 0,
            "archived": 0,
            "errors": 0,
        }

    async def start(self) -> None:
        """Start consuming from all dead-letter topics."""
        for topic in self._source_topics:
            dlq_topic = f"{topic}-dead-letter"
            await self._client.start_consumer(
                topic=dlq_topic,
                handler=self._handle_dlq_message,
                consumer_group="dlq-processor",
            )
            logger.info("DLQ consumer started for topic=%s", dlq_topic)

    async def stop(self) -> None:
        """Stop all DLQ consumers."""
        for topic in self._source_topics:
            dlq_topic = f"{topic}-dead-letter"
            await self._client.stop_consumer(dlq_topic)
        logger.info("DLQ consumers stopped")

    async def _handle_dlq_message(self, message: dict) -> None:
        """Process a single dead-letter message."""
        self._stats["consumed"] += 1

        dlq_record = self._build_dlq_record(message)

        logger.warning(
            "DLQ message consumed: event_id=%s source=%s reason=%s",
            dlq_record.get("original_event_id", "unknown"),
            dlq_record.get("source_topic", "unknown"),
            dlq_record.get("failure_reason", "unknown"),
        )

        if self._custom_handler:
            try:
                await self._custom_handler(dlq_record)
            except Exception:
                logger.exception("Custom DLQ handler failed")
                self._stats["errors"] += 1

        if self._es_client:
            await self._archive_to_elasticsearch(dlq_record)

    def _build_dlq_record(self, message: dict) -> dict:
        """Build a structured DLQ record from the raw message."""
        now = datetime.now(UTC)

        return {
            "dlq_timestamp": now.isoformat(),
            "original_event_id": message.get("event_id", message.get("message_id", "")),
            "source_topic": message.get("_dlq_source_topic", "unknown"),
            "failure_reason": message.get("_dlq_reason", "processing_failed"),
            "failure_count": message.get("_dlq_failure_count", 1),
            "first_failure_at": message.get("_dlq_first_failure", now.isoformat()),
            "payload": message,
            "schema_version": "1.0",
            "event_type": "dlq.dead_letter",
        }

    async def _archive_to_elasticsearch(self, record: dict) -> None:
        """Archive DLQ record to Elasticsearch for offline analysis."""
        try:
            index_name = f"magenta-dlq-{record['dlq_timestamp'][:10].replace('-', '.')}"
            await self._es_client.index(
                index=index_name,
                document=record,
            )
            self._stats["archived"] += 1
            logger.debug("DLQ record archived to index=%s", index_name)
        except Exception:
            logger.exception("Failed to archive DLQ record to Elasticsearch")
            self._stats["errors"] += 1

    def get_stats(self) -> dict:
        """Return DLQ consumer statistics."""
        return {**self._stats}
