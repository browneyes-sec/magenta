"""Linux syslog collector — HTTPS push receiver & SFTP poller."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from magenta.integration.collectors import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class LinuxSyslogCollector(BaseCollector):
    """Collects Linux syslog via HTTPS ingest API (primary) or SFTP (fallback)."""

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._ingest_endpoint = config.options.get("ingest_url", "")
        self._sftp_host = config.options.get("sftp_host", "")
        self._sftp_path = config.options.get("sftp_path", "/var/log/export")

    async def collect(self) -> list[dict]:
        if not self._running:
            return []

        if self._ingest_endpoint:
            return await self._collect_via_ingest()
        elif self._sftp_host:
            return await self._collect_via_sftp()
        return []

    async def _collect_via_ingest(self) -> list[dict]:
        """Push mode — Fluent Bit already sends to ingest API.
        This collector acts as a consumer-side validator; actual
        ingestion happens via the ingest API gateway."""
        logger.debug("Linux collector in push mode — awaiting events via Event Hubs")
        return []

    async def _collect_via_sftp(self) -> list[dict]:
        """Pull mode — read exported log files from SFTP staging."""
        # Placeholder: will use paramiko to list/pull .log/.json files
        logger.info("SFTP poll cycle for %s", self._sftp_host)
        return []

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "mode": "push" if self._ingest_endpoint else "pull",
            "running": self._running,
            "last_poll": datetime.now(timezone.utc).isoformat(),
        }
