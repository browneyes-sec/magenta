"""Linux syslog collector — SFTP/FTPS pull from log aggregator."""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any

from magenta.integration.collectors.base import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)


class LinuxSyslogCollector(BaseCollector):
    """Collects Linux syslog via SFTP pull from log aggregator.

    Connects to the configured SFTP/FTPS staging host and pulls
    log files matching the configured pattern. Supports both
    file-level and incremental (since last poll) collection.
    """

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._host = config.options.get("sftp_host", "")
        self._port = config.options.get("sftp_port", 22)
        self._username = config.options.get("sftp_username", "")
        self._key_path = config.options.get("ssh_key_path", "")
        self._key_data = config.options.get("ssh_key_data", "")
        self._remote_path = config.options.get("remote_path", "/var/log/export")
        self._file_pattern = config.options.get("file_pattern", "*.log")
        self._known_hosts = config.options.get("known_hosts_path", "")
        self._last_poll: str | None = None

    async def collect(self) -> list[dict]:
        if not self._running or not self._host:
            return []

        try:
            import paramiko
        except ImportError:
            logger.error("paramiko not installed — run 'uv sync --group collectors'")
            return []

        events: list[dict] = []
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(
                paramiko.AutoAddPolicy if not self._known_hosts
                else paramiko.RejectPolicy
            )
            if self._key_data:
                key = paramiko.RSAKey.from_private_key(io.StringIO(self._key_data))
                ssh.connect(self._host, port=self._port, username=self._username, pkey=key)
            elif self._key_path:
                ssh.connect(self._host, port=self._port, username=self._username, key_filename=self._key_path)
            else:
                ssh.connect(self._host, port=self._port, username=self._username)

            sftp = ssh.open_sftp()
            sftp.chdir(self._remote_path)

            files = sftp.listdir_attr(".")
            for attr in files:
                if not attr.filename.endswith((".log", ".json", ".syslog")):
                    continue
                if self._last_poll and attr.st_mtime < self._last_poll_timestamp():
                    continue

                with sftp.open(attr.filename, "r") as f:
                    raw = f.read().decode("utf-8", errors="replace")

                for line in raw.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    events.append({
                        "_collector": self.config.name,
                        "_source": f"sftp://{self._host}/{self._remote_path}/{attr.filename}",
                        "_raw": line,
                        "_mtime": datetime.fromtimestamp(attr.st_mtime, tz=timezone.utc).isoformat(),
                    })

            sftp.close()
            ssh.close()
            self._last_poll = datetime.now(timezone.utc).isoformat()
            logger.info("SFTP polled %d events from %d files", len(events), len(files))
        except Exception as e:
            logger.exception("SFTP poll failed for %s: %s", self._host, e)

        return events

    def _last_poll_timestamp(self) -> float:
        try:
            return datetime.fromisoformat(self._last_poll).timestamp()
        except (ValueError, TypeError):
            return 0

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "host": self._host,
            "port": self._port,
            "remote_path": self._remote_path,
            "running": self._running,
            "last_poll": self._last_poll,
        }
