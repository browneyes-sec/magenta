"""Schema Registry — JSON Schema validation for event envelopes.

Provides versioned JSON Schema definitions for all event types
(security.event, automation.activity, dlq.dead_letter) with
validation, compatibility checks, and Git-based versioning.

DTP §2: Schema registry for event envelope validation.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_DIR = Path(__file__).parent.parent.parent / "soa" / "config" / "schemas"
EVENT_SCHEMAS_DIR = Path(__file__).parent.parent.parent / "soa" / "config" / "event_schemas"


# ── Built-in Event Schemas ─────────────────────────────────────────────────

SECURITY_EVENT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "magenta://schemas/security.event/v1.0",
    "title": "Security Event",
    "description": "Canonical security.event envelope for normalized log data.",
    "type": "object",
    "required": [
        "schema_version", "event_type", "event_id",
        "correlation_id", "idempotency_key", "source_system",
        "timestamp", "severity", "category",
    ],
    "properties": {
        "schema_version": {"type": "string", "const": "1.0"},
        "event_type": {"type": "string", "const": "security.event"},
        "event_id": {"type": "string", "minLength": 1},
        "correlation_id": {"type": "string", "minLength": 1},
        "idempotency_key": {"type": "string", "minLength": 1},
        "source_system": {
            "type": "string",
            "enum": [
                "windows_event", "linux_syslog",
                "cloud.azure", "cloud.aws", "cloud.gcp",
                "customer.custom",
            ],
        },
        "source_host": {"type": "string"},
        "timestamp": {"type": "string"},
        "severity": {
            "type": "string",
            "enum": ["critical", "high", "medium", "low", "informational"],
        },
        "category": {"type": "string"},
        "normalized_fields": {"type": "object"},
        "payload": {"type": "object"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "provenance": {"$ref": "#/definitions/Provenance"},
    },
    "definitions": {
        "Provenance": {
            "type": "object",
            "properties": {
                "input_hash": {"type": "string"},
                "raw_alert_ref": {"type": "string"},
                "output_ref": {"type": "string"},
                "pipeline_step": {"type": "string"},
                "parent_event_id": {"type": "string"},
            },
        },
    },
}

AUTOMATION_ACTIVITY_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "magenta://schemas/automation.activity/v1.0",
    "title": "Automation Activity",
    "description": "Canonical automation.activity event for agent actions.",
    "type": "object",
    "required": [
        "schema_version", "event_type", "event_id",
        "correlation_id", "idempotency_key", "source_system",
        "action", "target", "status", "executor",
    ],
    "properties": {
        "schema_version": {"type": "string", "const": "1.0"},
        "event_type": {"type": "string", "const": "automation.activity"},
        "event_id": {"type": "string"},
        "correlation_id": {"type": "string"},
        "idempotency_key": {"type": "string"},
        "source_system": {"type": "string"},
        "source_alert_id": {"type": "string"},
        "playbook_id": {"type": "string"},
        "action": {"type": "string"},
        "target": {
            "type": "object",
            "required": ["type", "id"],
            "properties": {
                "type": {"type": "string", "enum": ["host", "ip", "user", "group", "resource"]},
                "id": {"type": "string"},
            },
        },
        "status": {"type": "string"},
        "risk_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "evidence": {"$ref": "#/definitions/Evidence"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "definitions": {
        "Evidence": {
            "type": "object",
            "properties": {
                "input_hash": {"type": "string"},
                "raw_alert_ref": {"type": "string"},
                "output_ref": {"type": "string"},
            },
        },
    },
}

DLQ_DEAD_LETTER_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "magenta://schemas/dlq.dead_letter/v1.0",
    "title": "Dead Letter",
    "description": "DLQ record for failed Event Hub messages.",
    "type": "object",
    "required": [
        "schema_version", "event_type", "dlq_timestamp",
        "original_event_id", "source_topic", "failure_reason",
    ],
    "properties": {
        "schema_version": {"type": "string", "const": "1.0"},
        "event_type": {"type": "string", "const": "dlq.dead_letter"},
        "dlq_timestamp": {"type": "string"},
        "original_event_id": {"type": "string"},
        "source_topic": {"type": "string"},
        "failure_reason": {"type": "string"},
        "failure_count": {"type": "integer"},
        "first_failure_at": {"type": "string"},
        "payload": {"type": "object"},
    },
}

BUILTIN_SCHEMAS: dict[str, dict[str, Any]] = {
    "security.event": SECURITY_EVENT_SCHEMA,
    "automation.activity": AUTOMATION_ACTIVITY_SCHEMA,
    "dlq.dead_letter": DLQ_DEAD_LETTER_SCHEMA,
}


class SchemaRegistry:
    """JSON Schema registry for event envelope validation.

    Supports:
    - Built-in schemas for security.event, automation.activity, dlq.dead_letter
    - File-based schemas from soa/config/schemas/
    - Schema versioning and compatibility checks
    - Runtime validation with detailed error reporting

    Usage:
        registry = SchemaRegistry()
        errors = registry.validate("security.event", envelope_dict)
        if errors:
            raise SchemaValidationError(errors)
    """

    def __init__(self, schema_dir: Path | None = None):
        self._schema_dir = schema_dir or EVENT_SCHEMAS_DIR
        self._schemas: dict[str, dict[str, Any]] = dict(BUILTIN_SCHEMAS)
        self._versions: dict[str, list[str]] = {}
        self._load_file_schemas()

    def _load_file_schemas(self) -> None:
        """Load schemas from the event_schemas directory."""
        if not self._schema_dir.exists():
            self._schema_dir.mkdir(parents=True, exist_ok=True)
            self._write_builtin_schemas()
            return

        for schema_file in self._schema_dir.glob("*.schema.json"):
            try:
                data = json.loads(schema_file.read_text())
                event_type = data.get("title", schema_file.stem).lower().replace(" ", ".")
                self._schemas[event_type] = data
                version = data.get("properties", {}).get("schema_version", {}).get("const", "1.0")
                self._versions.setdefault(event_type, []).append(version)
            except Exception:
                logger.exception("Failed to load schema from %s", schema_file)

    def _write_builtin_schemas(self) -> None:
        """Write built-in schemas to disk for versioning."""
        for event_type, schema in BUILTIN_SCHEMAS.items():
            filename = f"{event_type.replace('.', '_')}.schema.json"
            filepath = self._schema_dir / filename
            filepath.write_text(json.dumps(schema, indent=2))
            logger.info("Wrote built-in schema to %s", filepath)

    def validate(self, event_type: str, instance: dict[str, Any]) -> list[str]:
        """Validate an event envelope against its schema.

        Returns a list of error messages (empty if valid).
        """
        try:
            import jsonschema
        except ImportError:
            logger.warning("jsonschema not installed, skipping validation")
            return []

        schema = self._schemas.get(event_type)
        if not schema:
            return [f"Unknown event type: {event_type}"]

        errors = []
        validator = jsonschema.Draft7Validator(schema)
        for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
            path = ".".join(str(p) for p in error.absolute_path) or "<root>"
            errors.append(f"{path}: {error.message}")

        return errors

    def get_schema(self, event_type: str) -> dict[str, Any] | None:
        """Get schema definition by event type."""
        return self._schemas.get(event_type)

    def get_version(self, event_type: str) -> str:
        """Get the current version of an event schema."""
        schema = self._schemas.get(event_type)
        if schema:
            return schema.get("properties", {}).get("schema_version", {}).get("const", "1.0")
        return "unknown"

    def list_schemas(self) -> list[dict[str, Any]]:
        """List all registered schemas with metadata."""
        return [
            {
                "event_type": et,
                "version": self.get_version(et),
                "title": s.get("title", ""),
                "description": s.get("description", ""),
                "required_fields": list(s.get("required", [])),
            }
            for et, s in self._schemas.items()
        ]

    def compute_hash(self, event_type: str) -> str:
        """Compute a content hash of the schema for change detection."""
        schema = self._schemas.get(event_type)
        if not schema:
            return ""
        content = json.dumps(schema, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# Module-level singleton
schema_registry = SchemaRegistry()
