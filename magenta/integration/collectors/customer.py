"""Customer log collector — SFTP/HTTPS file drop adapter with schema-on-read."""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import UTC, datetime

from magenta.integration.collectors.base import BaseCollector, CollectorConfig

logger = logging.getLogger(__name__)

CEF_FIELD_RE = re.compile(r"(\w+)=([^=\s]+(?:\s+\S+)*?)(?=\s+\w+=|\s*$)")
CEF_HEADER_RE = re.compile(
    r"CEF:(\d+)\|([^|]+)\|([^|]+)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]+)"
)


class CustomerSFTPCollector(BaseCollector):
    """Collects customer log files from SFTP/FTPS drop locations.

    Supports CEF, JSON, CSV, and raw text files. Schema is inferred
    from file extension per TCF Gate 3 mapping.
    """

    def __init__(self, config: CollectorConfig):
        super().__init__(config)
        self._host = config.options.get("sftp_host", "")
        self._port = config.options.get("sftp_port", 22)
        self._username = config.options.get("sftp_username", "magenta-collector")
        self._key_path = config.options.get("ssh_key_path", "")
        self._key_data = config.options.get("ssh_key_data", "")
        self._drop_path = config.options.get("drop_path", "/incoming")
        self._file_pattern = config.options.get("file_pattern", "*.log")
        self._known_hosts = config.options.get("known_hosts_path", "")
        self._last_poll: str | None = None
        self._processed_files: set[str] = set()

    async def collect(self) -> list[dict]:
        if not self._running or not self._host:
            return []

        try:
            import paramiko
        except ImportError:
            logger.error("paramiko not installed")
            return []

        events: list[dict] = []
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(
            paramiko.AutoAddPolicy if not self._known_hosts
            else paramiko.RejectPolicy
        )
        try:
            if self._key_data:
                key = paramiko.RSAKey.from_private_key(io.StringIO(self._key_data))
                ssh.connect(self._host, port=self._port, username=self._username, pkey=key)
            elif self._key_path:
                ssh.connect(self._host, port=self._port, username=self._username, key_filename=self._key_path)
            else:
                ssh.connect(self._host, port=self._port, username=self._username)

            sftp = ssh.open_sftp()
            sftp.chdir(self._drop_path)

            for attr in sftp.listdir_attr("."):
                if attr.filename in self._processed_files:
                    continue
                if not self._matches_pattern(attr.filename):
                    continue

                with sftp.open(attr.filename, "r") as fh:
                    raw = fh.read().decode("utf-8", errors="replace")

                schema = await self.schema_from_filename(attr.filename)
                parsed = await self._parse_by_schema(raw, schema, attr.filename)

                for event in parsed:
                    event["_collector"] = self.config.name
                    event["_drop_path"] = f"sftp://{self._host}/{self._drop_path}/{attr.filename}"
                    event["_schema"] = schema
                events.extend(parsed)
                self._processed_files.add(attr.filename)

            sftp.close()
            ssh.close()
            self._last_poll = datetime.now(UTC).isoformat()
        except Exception as e:
            logger.exception("Customer SFTP poll failed for %s: %s", self._host, e)

        return events

    async def schema_from_filename(self, filename: str) -> str:
        if filename.endswith(".cef"):
            return "customer.cef"
        if filename.endswith(".json"):
            return "customer.json"
        if filename.endswith(".csv"):
            return "customer.csv"
        return "customer.raw"

    async def _parse_by_schema(self, raw: str, schema: str, filename: str) -> list[dict]:
        if schema == "customer.cef":
            return self._parse_cef(raw)
        if schema == "customer.json":
            return self._parse_jsonl(raw)
        if schema == "customer.csv":
            return self._parse_csv(raw)
        return self._parse_raw(raw, filename)

    def _parse_cef(self, raw: str) -> list[dict]:
        events: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            m = CEF_HEADER_RE.match(line)
            if not m:
                logger.debug("Skipping non-CEF line")
                continue
            header = {
                "cef_version": m.group(1),
                "device_vendor": m.group(2),
                "device_product": m.group(3),
                "device_version": m.group(4),
                "signature_id": m.group(5),
                "name": m.group(6),
                "severity": m.group(7),
            }
            ext = {}
            for k, v in CEF_FIELD_RE.findall(m.group()):
                ext[k] = v
            events.append({**header, "extensions": ext})
        return events

    def _parse_jsonl(self, raw: str) -> list[dict]:
        events: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                logger.debug("Skipping invalid JSON line")
        return events

    def _parse_csv(self, raw: str) -> list[dict]:
        events: list[dict] = []
        reader = csv.DictReader(io.StringIO(raw))
        for row in reader:
            events.append(dict(row))
        return events

    def _parse_raw(self, raw: str, filename: str) -> list[dict]:
        return [
            {"_raw": line.strip(), "_source_file": filename}
            for line in raw.splitlines()
            if line.strip()
        ]

    def _matches_pattern(self, filename: str) -> bool:
        pattern = self._file_pattern
        if pattern == "*" or pattern == "*.*":
            return True
        if pattern.startswith("*."):
            return filename.endswith(pattern[1:])
        return filename == pattern

    async def health(self) -> dict:
        return {
            "collector": self.config.name,
            "source_type": self.config.source_type,
            "sftp_host": self._host,
            "drop_path": self._drop_path,
            "file_pattern": self._file_pattern,
            "running": self._running,
            "last_poll": self._last_poll,
            "processed_files": len(self._processed_files),
        }
