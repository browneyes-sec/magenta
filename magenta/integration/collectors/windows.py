"""Windows Event Log collector — WAC gateway & WinRM-SSL."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from magenta.integration.collectors import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class WindowsEventCollector(BaseCollector):
    """Collects Windows Event Log via WAC gateway (primary) or WinRM-SSL (fallback)."""

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._wac_endpoint = config.options.get("wac_url", "")
        self._winrm_host = config.options.get("winrm_host", "")
        self._winrm_port = config.options.get("winrm_port", 5986)
        self._event_logs = config.options.get("event_logs", [
            "Security", "System", "Application",
        ])

    async def collect(self) -> list[dict]:
        if not self._running:
            return []

        if self._wac_endpoint:
            return await self._collect_via_wac()
        elif self._winrm_host:
            return await self._collect_via_winrm()
        return []

    async def _collect_via_wac(self) -> list[dict]:
        """Pull events via WAC REST gateway (HTTPS)."""
        logger.debug("WAC poll cycle for %s — logs: %s", self._wac_endpoint, self._event_logs)
        return []

    async def _collect_via_winrm(self) -> list[dict]:
        """Pull events via WinRM over SSL (port 5986)."""
        logger.debug("WinRM poll cycle for %s:%s", self._winrm_host, self._winrm_port)
        return []

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "mode": "wac" if self._wac_endpoint else "winrm",
            "running": self._running,
            "last_poll": datetime.now(timezone.utc).isoformat(),
        }
