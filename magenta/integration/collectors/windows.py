"""Windows Event Log collector — WinRM-SSL and WAC gateway."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from magenta.integration.collectors.base import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class WindowsEventCollector(BaseCollector):
    """Collects Windows Event Log via WinRM over SSL (primary) or WAC (fallback).

    Uses pywinrm to execute PowerShell ``Get-WinEvent`` queries on
    remote Windows hosts. Supports Security, System, Application, and
    custom event logs.
    """

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._host = config.options.get("host", "")
        self._port = config.options.get("winrm_port", 5986)
        self._username = config.options.get("username", "")
        self._password = config.options.get("password", "")
        self._use_ssl = config.options.get("use_ssl", True)
        self._transport = config.options.get("transport", "ssl")  # ssl | kerberos | ntlm
        self._event_logs = config.options.get("event_logs", [
            "Security", "System", "Application",
        ])
        self._max_events = config.options.get("max_events_per_log", 500)
        self._lookback_hours = config.options.get("lookback_hours", 24)
        self._last_poll: str | None = None

    async def collect(self) -> list[dict]:
        if not self._running or not self._host:
            return []

        try:
            import winrm
        except ImportError:
            logger.error("pywinrm not installed — run 'uv sync --group collectors'")
            return []

        events: list[dict] = []
        protocol = "https" if self._use_ssl else "http"
        endpoint = f"{protocol}://{self._host}:{self._port}/wsman"

        try:
            session = winrm.Session(
                endpoint,
                auth=(self._username, self._password),
                transport=self._transport,
                server_cert_validation="ignore",
            )

            for log_name in self._event_logs:
                script = self._build_event_query(log_name)
                result = session.run_ps(script)
                if result.status_code != 0:
                    logger.warning("WinRM query failed for %s: %s", log_name, result.std_err[:200])
                    continue

                for line in result.std_out.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    events.append({
                        "_collector": self.config.name,
                        "_host": self._host,
                        "_log": log_name,
                        "_raw": line,
                        "_polled_at": datetime.now(UTC).isoformat(),
                    })

            self._last_poll = datetime.now(UTC).isoformat()
            logger.info("WinRM polled %d events from %s logs=%s", len(events), self._host, self._event_logs)
        except Exception as e:
            logger.exception("WinRM poll failed for %s: %s", self._host, e)

        return events

    def _build_event_query(self, log_name: str) -> str:
        """Generate PowerShell Get-WinEvent script for a given log."""
        return f"""
$Events = Get-WinEvent -LogName '{log_name}' -MaxEvents {self._max_events} -ErrorAction SilentlyContinue
if (-not $Events) {{ exit 0 }}
$Events | ForEach-Object {{
    $xml = $_.ToXml()
    Write-Output ($xml.OuterXml)
}}
"""

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "host": self._host,
            "port": self._port,
            "transport": self._transport,
            "event_logs": self._event_logs,
            "running": self._running,
            "last_poll": self._last_poll,
        }
