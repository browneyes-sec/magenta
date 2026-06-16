"""Avro Schema Registry — binary-optimized event schemas.

Provides Avro schema definitions for high-throughput event topics,
compatible with Confluent Schema Registry and Apache Avro.

DTP §E4: Avro Schema Registry.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_DIR = Path(__file__).parent.parent.parent / "soa" / "config" / "avro_schemas"


# ── Built-in Avro Schemas ─────────────────────────────────────────────────

SECURITY_EVENT_AVRO: dict[str, Any] = {
    "type": "record",
    "name": "SecurityEvent",
    "namespace": "magenta.events",
    "doc": "Canonical security.event envelope for normalized log data.",
    "fields": [
        {"name": "schema_version", "type": "string", "default": "1.0"},
        {"name": "event_type", "type": "string", "default": "security.event"},
        {"name": "event_id", "type": "string"},
        {"name": "correlation_id", "type": "string"},
        {"name": "idempotency_key", "type": "string"},
        {
            "name": "source_system",
            "type": {
                "type": "enum",
                "name": "SourceSystem",
                "symbols": [
                    "windows_event", "linux_syslog",
                    "cloud_azure", "cloud_aws", "cloud_gcp",
                    "customer_custom",
                ],
            },
        },
        {"name": "source_host", "type": "string", "default": ""},
        {"name": "timestamp", "type": "string"},
        {
            "name": "severity",
            "type": {
                "type": "enum",
                "name": "Severity",
                "symbols": ["critical", "high", "medium", "low", "informational"],
            },
        },
        {"name": "category", "type": "string"},
        {
            "name": "normalized_fields",
            "type": {"type": "map", "values": "string"},
            "default": {},
        },
        {
            "name": "tags",
            "type": {"type": "array", "items": "string"},
            "default": [],
        },
        {
            "name": "provenance",
            "type": ["null", {
                "type": "record",
                "name": "Provenance",
                "fields": [
                    {"name": "pipeline_step", "type": "string", "default": ""},
                    {"name": "input_hash", "type": "string", "default": ""},
                    {"name": "raw_alert_ref", "type": ["null", "string"], "default": None},
                    {"name": "output_ref", "type": ["null", "string"], "default": None},
                ],
            }],
            "default": None,
        },
    ],
}

AUTOMATION_ACTIVITY_AVRO: dict[str, Any] = {
    "type": "record",
    "name": "AutomationActivity",
    "namespace": "magenta.events",
    "doc": "Canonical automation.activity event for agent actions.",
    "fields": [
        {"name": "schema_version", "type": "string", "default": "1.0"},
        {"name": "event_type", "type": "string", "default": "automation.activity"},
        {"name": "event_id", "type": "string"},
        {"name": "correlation_id", "type": "string"},
        {"name": "idempotency_key", "type": "string"},
        {"name": "source_system", "type": "string"},
        {"name": "source_alert_id", "type": "string", "default": ""},
        {"name": "playbook_id", "type": "string", "default": ""},
        {"name": "action", "type": "string"},
        {
            "name": "target",
            "type": {
                "type": "record",
                "name": "Target",
                "fields": [
                    {"name": "type", "type": "string"},
                    {"name": "id", "type": "string"},
                ],
            },
        },
        {"name": "status", "type": "string"},
        {"name": "risk_score", "type": "int", "default": 0},
        {
            "name": "evidence",
            "type": ["null", {
                "type": "record",
                "name": "Evidence",
                "fields": [
                    {"name": "input_hash", "type": ["null", "string"], "default": None},
                    {"name": "raw_alert_ref", "type": ["null", "string"], "default": None},
                    {"name": "output_ref", "type": ["null", "string"], "default": None},
                ],
            }],
            "default": None,
        },
        {
            "name": "tags",
            "type": {"type": "array", "items": "string"},
            "default": [],
        },
    ],
}

CDC_CHANGE_AVRO: dict[str, Any] = {
    "type": "record",
    "name": "CDCChange",
    "namespace": "magenta.events",
    "doc": "CDC change event from database capture.",
    "fields": [
        {"name": "event_id", "type": "string"},
        {"name": "source_type", "type": "string"},
        {"name": "database", "type": "string"},
        {"name": "collection", "type": "string"},
        {"name": "operation", "type": "string"},
        {"name": "document_id", "type": "string"},
        {
            "name": "before",
            "type": {"type": "map", "values": "string"},
            "default": {},
        },
        {
            "name": "after",
            "type": {"type": "map", "values": "string"},
            "default": {},
        },
        {"name": "timestamp", "type": "string"},
        {"name": "captured_at", "type": "double"},
        {"name": "schema_version", "type": "string", "default": "1.0"},
        {"name": "event_type", "type": "string", "default": "cdc.change"},
    ],
}

BUILTIN_AVRO_SCHEMAS: dict[str, dict[str, Any]] = {
    "security.event": SECURITY_EVENT_AVRO,
    "automation.activity": AUTOMATION_ACTIVITY_AVRO,
    "cdc.change": CDC_CHANGE_AVRO,
}


class AvroSchemaRegistry:
    """Avro schema registry for binary-optimized event serialization.

    Provides:
    - Avro schema definitions for all event types
    - Schema compatibility checks
    - Content-hash based versioning
    - JSON-to-Avro conversion helpers
    """

    def __init__(self, schema_dir: Path | None = None):
        self._schema_dir = schema_dir or SCHEMA_DIR
        self._schemas: dict[str, dict[str, Any]] = dict(BUILTIN_AVRO_SCHEMAS)
        self._versions: dict[str, str] = {}
        self._load_file_schemas()

    def _load_file_schemas(self) -> None:
        """Load schemas from the avro_schemas directory."""
        if not self._schema_dir.exists():
            self._schema_dir.mkdir(parents=True, exist_ok=True)
            self._write_builtin_schemas()
            return

        for schema_file in self._schema_dir.glob("*.avsc"):
            try:
                data = json.loads(schema_file.read_text())
                name = data.get("name", schema_file.stem)
                event_type = name.lower().replace("_", ".")
                self._schemas[event_type] = data
            except Exception:
                logger.exception("Failed to load Avro schema from %s", schema_file)

    def _write_builtin_schemas(self) -> None:
        """Write built-in schemas to disk."""
        for event_type, schema in BUILTIN_AVRO_SCHEMAS.items():
            filename = f"{event_type.replace('.', '_')}.avsc"
            filepath = self._schema_dir / filename
            filepath.write_text(json.dumps(schema, indent=2))
            logger.info("Wrote built-in Avro schema to %s", filepath)

    def get_schema(self, event_type: str) -> dict[str, Any] | None:
        """Get Avro schema by event type."""
        return self._schemas.get(event_type)

    def get_schema_str(self, event_type: str) -> str:
        """Get Avro schema as JSON string."""
        schema = self._schemas.get(event_type)
        return json.dumps(schema) if schema else ""

    def compute_hash(self, event_type: str) -> str:
        """Compute content hash of the schema."""
        schema = self._schemas.get(event_type)
        if not schema:
            return ""
        content = json.dumps(schema, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def list_schemas(self) -> list[dict[str, Any]]:
        """List all registered Avro schemas."""
        return [
            {
                "event_type": et,
                "name": s.get("name", ""),
                "namespace": s.get("namespace", ""),
                "doc": s.get("doc", ""),
                "fields": len(s.get("fields", [])),
                "hash": self.compute_hash(et),
            }
            for et, s in self._schemas.items()
        ]

    def validate_compatible(self, event_type: str, new_schema: dict[str, Any]) -> bool:
        """Check if a new schema is backward-compatible."""
        existing = self._schemas.get(event_type)
        if not existing:
            return True

        existing_fields = {f["name"] for f in existing.get("fields", [])}
        new_fields = {f["name"] for f in new_schema.get("fields", [])}

        removed = existing_fields - new_fields
        if removed:
            logger.warning(
                "Schema incompatibility for %s: removed fields %s",
                event_type, removed,
            )
            return False

        return True

    def register(self, event_type: str, schema: dict[str, Any]) -> str:
        """Register a new schema. Returns the schema hash."""
        if not self.validate_compatible(event_type, schema):
            raise ValueError(f"Schema incompatible with existing {event_type}")

        self._schemas[event_type] = schema
        schema_hash = self.compute_hash(event_type)
        self._versions[event_type] = schema_hash

        self._write_schema(event_type, schema)
        logger.info("Avro schema registered: %s (hash=%s)", event_type, schema_hash)
        return schema_hash

    def _write_schema(self, event_type: str, schema: dict[str, Any]) -> None:
        """Write schema to disk."""
        filename = f"{event_type.replace('.', '_')}.avsc"
        filepath = self._schema_dir / filename
        filepath.write_text(json.dumps(schema, indent=2))


# Module-level singleton
avro_registry = AvroSchemaRegistry()
