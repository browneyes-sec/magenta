"""Log Normalizer — transforms raw log payloads into security.event schema."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from magenta.exceptions import IntegrationError
from magenta.integration.eventhub import IdempotencyGuard

logger = logging.getLogger(__name__)

# ── Source Detection ───────────────────────────────────────────────────────

WINDOWS_EVENT_PATTERNS = [
    re.compile(r"Event\s*ID\s*\d+", re.I),
    re.compile(r"<Event[> ]"),
    re.compile(r"System/EventID"),
]

SYSLOG_PRIORITY_RE = re.compile(r"<(\d+)>")


def detect_source(payload: dict, raw_body: str = "") -> str:
    """Detect source_system from payload shape or raw text."""
    if any(p.search(str(payload)) for p in WINDOWS_EVENT_PATTERNS):
        return "windows_event"
    if SYSLOG_PRIORITY_RE.match(raw_body.lstrip()):
        return "linux_syslog"
    if "Records" in payload or "operationName" in payload:
        return "cloud.azure"
    if "Records" in payload and "eventSource" in payload.get("Records", [{}])[0]:
        return "cloud.aws"
    if "insertId" in payload or "jsonPayload" in payload:
        return "cloud.gcp"
    return "customer.custom"


# ── Field Mappers ──────────────────────────────────────────────────────────

class WindowsEventMapper:
    """Normalize Windows Event XML → security.event."""

    SEVERITY_MAP = {"1": "critical", "2": "high", "3": "medium", "4": "low", "0": "informational"}

    @classmethod
    def map(cls, payload: dict) -> dict:
        system = payload.get("System", payload)
        event_data = payload.get("EventData", {}).get("Data", [])
        data_map = {d.get("" if isinstance(d, str) else d.get("@Name", "")).replace("{", "").replace("}", ""):
                    d.get("#text", d) if isinstance(d, dict) else d
                    for d in (event_data if isinstance(event_data, list) else [])}

        severity_num = str(system.get("Level", "4"))
        data_map = {}
        raw_data = payload.get("EventData", {})
        if isinstance(raw_data, dict):
            raw_list = raw_data.get("Data", [])
            if isinstance(raw_list, list):
                for item in raw_list:
                    if isinstance(item, dict):
                        name = item.get("@Name", "")
                        val = item.get("#text", "")
                        data_map[name] = val

        return {
            "normalized_fields": {
                "EventID": str(system.get("EventID", "")),
                "ActorUsername": data_map.get("SubjectUserName", ""),
                "TargetIPAddress": data_map.get("IpAddress", ""),
                "ProcessName": data_map.get("ProcessName", ""),
            },
            "source_host": str(system.get("Computer", "")),
            "timestamp": _parse_xml_time(str(system.get("TimeCreated", {}).get("@SystemTime", ""))),
            "severity": cls.SEVERITY_MAP.get(severity_num, "informational"),
            "category": _classify_event_id(str(system.get("EventID", ""))),
            "tags": ["provider:" + str(system.get("Provider", {}).get("@Name", "unknown"))],
        }


class SyslogMapper:
    """Normalize syslog messages → security.event."""

    SEVERITY_MAP = {
        0: "critical", 1: "critical", 2: "critical",
        3: "high", 4: "high",
        5: "medium",
        6: "low", 7: "informational",
    }

    @classmethod
    def map(cls, payload: dict, raw_line: str = "") -> dict:
        pri_match = SYSLOG_PRIORITY_RE.match(raw_line)
        severity = "informational"
        if pri_match:
            code = int(pri_match.group(1))
            severity = cls.SEVERITY_MAP.get(code & 7, "informational")

        msg = payload.get("message", payload.get("MSG", raw_line))
        hostname = payload.get("hostname", payload.get("HOSTNAME", ""))
        app = payload.get("app_name", payload.get("APP-NAME", ""))

        return {
            "normalized_fields": {
                "EventID": "",
                "ActorUsername": cls._extract_user(str(msg)),
                "TargetIPAddress": cls._extract_ip(str(msg)),
                "ProcessName": app,
            },
            "source_host": hostname,
            "timestamp": payload.get("timestamp", payload.get("TIMESTAMP", "")),
            "severity": severity,
            "category": _classify_syslog_msg(str(msg)),
            "tags": ["application:" + app],
        }

    @staticmethod
    def _extract_user(msg: str) -> str:
        m = re.search(r"(?:user|USER)\s+(\S+)", msg)
        return m.group(1) if m else ""

    @staticmethod
    def _extract_ip(msg: str) -> str:
        m = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", msg)
        return m.group(0) if m else ""


class CloudMapper:
    """Normalize cloud audit logs (Azure/AWS/GCP) → security.event."""

    @classmethod
    def map(cls, payload: dict) -> dict:
        records = payload.get("Records", [payload])
        if isinstance(records, dict):
            records = [records]
        record = records[0] if records else payload

        source_system = "cloud.azure"

        if "eventSource" in record:
            source_system = "cloud.aws"
        if "jsonPayload" in payload or "insertId" in payload:
            source_system = "cloud.gcp"
            record = payload

        if source_system == "cloud.azure":
            return cls._map_azure(record)
        elif source_system == "cloud.aws":
            return cls._map_aws(record)
        else:
            return cls._map_gcp(payload)

    @staticmethod
    def _map_azure(record: dict) -> dict:
        identity = record.get("identity", {}) or {}
        claims = identity.get("claims", {}) if isinstance(identity, dict) else {}

        return {
            "normalized_fields": {
                "EventID": record.get("correlationId", ""),
                "ActorUsername": claims.get("name", claims.get("upn", "")),
                "TargetIPAddress": record.get("callerIpAddress", ""),
                "ProcessName": "",
            },
            "source_host": "",
            "timestamp": record.get("eventTimestamp", record.get("time", "")),
            "severity": _azure_severity(record.get("level", "")),
            "category": record.get("operationName", "").split("/")[-1] if "/" in record.get("operationName", "") else record.get("operationName", ""),
            "tags": ["resource:" + record.get("resourceId", "").split("/")[-1]],
        }

    @staticmethod
    def _map_aws(record: dict) -> dict:
        return {
            "normalized_fields": {
                "EventID": record.get("eventID", ""),
                "ActorUsername": record.get("userIdentity", {}).get("arn", ""),
                "TargetIPAddress": record.get("sourceIPAddress", ""),
                "ProcessName": record.get("eventSource", ""),
            },
            "source_host": "",
            "timestamp": record.get("eventTime", ""),
            "severity": "informational",
            "category": record.get("eventName", ""),
            "tags": ["aws_region:" + record.get("awsRegion", "")],
        }

    @staticmethod
    def _map_gcp(payload: dict) -> dict:
        proto = payload.get("protoPayload", {}) or {}
        return {
            "normalized_fields": {
                "EventID": payload.get("insertId", ""),
                "ActorUsername": proto.get("authenticationInfo", {}).get("principalEmail", ""),
                "TargetIPAddress": proto.get("requestMetadata", {}).get("callerIp", ""),
                "ProcessName": proto.get("serviceName", ""),
            },
            "source_host": "",
            "timestamp": payload.get("timestamp", payload.get("receiveTimestamp", "")),
            "severity": payload.get("severity", "informational").lower(),
            "category": proto.get("methodName", "").split(".")[-1],
            "tags": ["resource:" + payload.get("resource", {}).get("type", "")],
        }


MAPPERS = {
    "windows_event": WindowsEventMapper,
    "linux_syslog": SyslogMapper,
    "cloud.azure": CloudMapper,
    "cloud.aws": CloudMapper,
    "cloud.gcp": CloudMapper,
    "customer.custom": None,
}


# ── Normalizer ─────────────────────────────────────────────────────────────

class LogNormalizer:
    """Transforms raw log payloads into canonical security.event schema."""

    def __init__(
        self,
        guard: IdempotencyGuard | None = None,
        redact_pii: bool = True,
    ):
        self._guard = guard
        self._redact_pii = redact_pii

    async def normalize(
        self,
        raw_event: dict,
        raw_body: str = "",
    ) -> Optional[dict]:
        source = detect_source(raw_event, raw_body)
        mapper_cls = MAPPERS.get(source)

        if mapper_cls is None:
            logger.warning("No mapper for source=%s, passing through raw payload", source)
            return self._build_envelope(raw_event, source, {})

        if source == "linux_syslog":
            mapped = SyslogMapper.map(raw_event, raw_body)
        else:
            mapped = mapper_cls.map(raw_event)

        envelope = self._build_envelope(raw_event, source, mapped)

        idem_key = envelope["idempotency_key"]
        if self._guard:
            duplicate = await self._guard.is_duplicate(idem_key)
            if duplicate:
                logger.debug("Duplicate event dropped idem_key=%s", idem_key[:16])
                return None

        return envelope

    def _build_envelope(self, raw: dict, source: str, mapped: dict) -> dict:
        event_id = str(uuid4())
        merged = {**raw.get("normalized_fields", {}), **mapped.get("normalized_fields", {})}

        timestamp = mapped.get("timestamp") or raw.get("timestamp", "")
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        idem_raw = f"{source}|{timestamp}|{mapped.get('source_host', '')}|{merged.get('EventID', event_id[:8])}"
        idempotency_key = hashlib.sha256(idem_raw.encode()).hexdigest()

        return {
            "schema_version": "1.0",
            "event_type": "security.event",
            "event_id": event_id,
            "correlation_id": hashlib.sha256(
                f"{source}|{mapped.get('source_host', '')}".encode()
            ).hexdigest()[:16],
            "idempotency_key": idempotency_key,
            "source_system": source,
            "source_host": mapped.get("source_host", ""),
            "timestamp": timestamp,
            "severity": mapped.get("severity", "informational"),
            "category": mapped.get("category", ""),
            "normalized_fields": merged,
            "tags": mapped.get("tags", []),
        }


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_xml_time(xml_time: str) -> str:
    try:
        dt = datetime.strptime(xml_time, "%Y-%m-%dT%H:%M:%S.%fZ")
        return dt.isoformat()
    except (ValueError, TypeError):
        return xml_time


def _classify_event_id(event_id: str) -> str:
    eid = event_id.lstrip("0")
    try:
        num = int(eid)
        if 4624 <= num <= 4625 or 4648 <= num <= 4649 or 4776 <= num <= 4778:
            return "authentication"
        if 5140 <= num <= 5145 or 5152 <= num <= 5159:
            return "network"
        if 4688 == num or 4697 == num:
            return "process"
        if 4719 == num or 1102 == num or 104 == num:
            return "audit"
        return "audit"
    except ValueError:
        return "audit"


def _classify_syslog_msg(msg: str) -> str:
    msg_lower = msg.lower()
    if "sshd" in msg_lower or "sudo" in msg_lower or "pam" in msg_lower or "login" in msg_lower:
        return "authentication"
    if "connection" in msg_lower or "port" in msg_lower or "dhcp" in msg_lower:
        return "network"
    if "cron" in msg_lower or "systemd" in msg_lower:
        return "process"
    return "application"


def _azure_severity(level: str) -> str:
    mapping = {
        "Critical": "critical", "Error": "high",
        "Warning": "medium", "Informational": "informational",
        "Verbose": "informational",
    }
    return mapping.get(level, "informational")
