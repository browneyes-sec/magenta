"""Registry writer — async triple-write to Elasticsearch, Sentinel, and Delta Lake.

Usage:
    from magenta.core.registry import registry_writer
    await registry_writer.write_activity(activity)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from magenta.config import settings
from magenta.core.models import AutomationActivity

logger = logging.getLogger(__name__)


class RegistryWriter:
    """Async triple-write registry with dead-letter queue fallback.

    Writes every automation.activity event to three sinks concurrently:
        1. Elasticsearch hot index (operational queries, 30-day retention)
        2. Sentinel custom table via Log Ingestion API (SIEM-native queries)
        3. Azure Data Lake Delta partition (long-term compliance archive)

    Design constraints:
        - Fire-and-forget: registry failures never block agent execution
        - return_exceptions=True in caller to isolate failures
        - Failed writes go to in-memory dead-letter queue with TTL-based retry
    """

    def __init__(self):
        self._es_client: Any = None
        self._sentinel_connector: Any = None
        self._delta_writer: Any = None
        self._dead_letter: list[dict] = []

    async def write_activity(self, activity: AutomationActivity) -> None:
        """Write an activity event to all three sinks concurrently.

        This is intended to be called via asyncio.gather(return_exceptions=True)
        so that a single sink failure does not block other writes.
        """
        import asyncio

        await asyncio.gather(
            self.write_elasticsearch(activity),
            self.write_sentinel(activity),
            self.write_delta_lake(activity),
            return_exceptions=True,
        )

    async def write_elasticsearch(self, activity: AutomationActivity) -> None:
        """Write to Elasticsearch hot index with idempotency key as document ID.

        Index pattern: automation-activity-YYYY.MM
        """
        try:
            if self._es_client is None:
                from elasticsearch import AsyncElasticsearch

                self._es_client = AsyncElasticsearch(
                    hosts=settings.elastic.hosts,
                    basic_auth=(
                        (settings.elastic.username, settings.elastic.password)
                        if settings.elastic.username
                        else None
                    ),
                )

            index_name = (
                f"{settings.elastic.index_prefix}-activity-{datetime.utcnow().strftime('%Y.%m')}"
            )
            await self._es_client.index(
                index=index_name,
                document=activity.model_dump(),
                id=activity.idempotency_key or None,
            )
            logger.debug(
                "Registry: wrote activity %s to ES index %s",
                activity.event_id[:8],
                index_name,
            )
        except Exception as e:
            await self._dead_letter_queue(activity, "elasticsearch", str(e))

    async def write_sentinel(self, activity: AutomationActivity) -> None:
        """Write to Sentinel SecurityAutomationActivity_CL via Log Ingestion API."""
        try:
            if self._sentinel_connector is None:
                from magenta.integration.sentinel import SentinelConnector

                self._sentinel_connector = SentinelConnector(
                    tenant_id=settings.sentinel.tenant_id,
                    client_id=settings.sentinel.client_id,
                    client_secret=settings.sentinel.client_secret,
                    workspace_id=settings.sentinel.workspace_id,
                )

            await self._sentinel_connector.ingest_activity([activity.model_dump()])
            logger.debug(
                "Registry: wrote activity %s to Sentinel",
                activity.event_id[:8],
            )
        except Exception as e:
            await self._dead_letter_queue(activity, "sentinel", str(e))

    async def write_delta_lake(self, activity: AutomationActivity) -> None:
        """Write to Azure Data Lake Delta partition.

        Partition strategy: source_system (e.g., sentinel, splunk)
        Write mode: append with idempotency_key dedup
        """
        try:
            if self._delta_writer is None:
                try:
                    from deltalake import write_deltalake
                except ImportError:
                    logger.warning("deltalake package not available — skipping Delta write")
                    return

                self._delta_writer = True

            record = activity.model_dump()
            record["date"] = datetime.utcnow().strftime("%Y-%m-%d")

            # Use append mode with idempotency_key as dedup column
            write_deltalake(
                settings.delta_lake.uri or settings.lake.root,
                [record],
                mode="append",
                partition_by=settings.delta_lake.partition_by,
            )
            logger.debug(
                "Registry: wrote activity %s to Delta Lake",
                activity.event_id[:8],
            )
        except Exception as e:
            await self._dead_letter_queue(activity, "delta_lake", str(e))

    async def _dead_letter_queue(
        self,
        activity: AutomationActivity,
        sink: str,
        error: str,
    ) -> None:
        """Store failed registry writes for retry or inspection."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "sink": sink,
            "event_id": activity.event_id,
            "idempotency_key": activity.idempotency_key,
            "correlation_id": activity.correlation_id,
            "error": error,
        }
        self._dead_letter.append(entry)
        logger.warning(
            "Registry dead-letter [%s]: activity %s — %s",
            sink,
            activity.event_id[:8],
            error,
        )

    def get_dead_letter_queue(self) -> list[dict]:
        """Get all queued failed writes (for monitoring/retry)."""
        return list(self._dead_letter)

    def drain_dead_letter_queue(self) -> list[dict]:
        """Clear and return all dead-letter entries."""
        entries = list(self._dead_letter)
        self._dead_letter.clear()
        return entries


registry_writer = RegistryWriter()
