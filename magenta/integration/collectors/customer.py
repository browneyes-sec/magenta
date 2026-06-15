"""Customer log collector — SFTP/HTTPS file drop adapter."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from magenta.integration.collectors import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class CustomerSFTPCollector(BaseCollector):
    """Collects customer log files from SFTP/FTPS drop locations."""

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._host = config.options.get("sftp_host", "")
        self._path = config.options.get("drop_path", "/incoming")
        self._file_pattern = config.options.get("file_pattern", "*.log")
        self._known_hosts = config.options.get("known_hosts_path", "")

    async def collect(self) -> list[dict]:
        if not self._running:
            return []
        logger.debug("SFTP poll for %s:%s", self._host, self._path)
        return []

    async def schema_from_filename(self, filename: str) -> str:
        """Infer canonical schema mapping from file extension/naming."""
        if filename.endswith(".cef"):
            return "customer.cef"
        if filename.endswith(".json"):
            return "customer.json"
        if filename.endswith(".csv"):
            return "customer.csv"
        return "customer.raw"

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "sftp_host": self._host,
            "drop_path": self._path,
            "running": self._running,
        }
