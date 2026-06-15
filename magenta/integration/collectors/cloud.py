"""Cloud log collectors — Azure DCR, AWS CloudTrail, GCP Cloud Logging."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from azure.identity.aio import DefaultAzureCredential

from magenta.integration.collectors import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class AzureDCRCollector(BaseCollector):
    """Collects Azure Monitor / Log Analytics logs via DCR + Event Hubs."""

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._workspace_id = config.options.get("workspace_id", "")
        self._credential = DefaultAzureCredential()

    async def collect(self) -> list[dict]:
        if not self._running:
            return []
        logger.debug("Azure DCR collect cycle for workspace=%s", self._workspace_id)
        # In push mode, events arrive via Event Hubs consumer;
        # this is a placeholder for diagnostic settings validation.
        return []

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "workspace_id": self._workspace_id[-8:] if len(self._workspace_id) > 8 else "unknown",
            "running": self._running,
        }


class AWSCloudTrailCollector(BaseCollector):
    """Collects AWS CloudTrail logs via S3 → EventBridge → Event Hubs."""

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._bucket = config.options.get("s3_bucket", "")
        self._prefix = config.options.get("s3_prefix", "AWSLogs/")

    async def collect(self) -> list[dict]:
        if not self._running:
            return []
        logger.debug("CloudTrail collect cycle for bucket=%s", self._bucket)
        return []

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "bucket": self._bucket,
            "running": self._running,
        }


class GCPLoggingCollector(BaseCollector):
    """Collects GCP Cloud Logging via Pub/Sub → Event Hubs bridge."""

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._project = config.options.get("gcp_project", "")
        self._subscription = config.options.get("pubsub_subscription", "")

    async def collect(self) -> list[dict]:
        if not self._running:
            return []
        logger.debug("GCP logging collect cycle for project=%s", self._project)
        return []

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "project": self._project,
            "running": self._running,
        }
