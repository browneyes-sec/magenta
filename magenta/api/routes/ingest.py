"""API routes — log ingest endpoint (HTTPS with HMAC/mTLS auth)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from magenta.exceptions import IntegrationError
from magenta.gateway.redact import RedactionLayer
from magenta.integration.eventhub import EventHubClient, HMACAuth, IdempotencyGuard

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy-init globals (set via init_ingest)
_client: EventHubClient | None = None
_hmac: HMACAuth | None = None
_guard: IdempotencyGuard | None = None
_redact: RedactionLayer | None = None


def init_ingest(
    client: EventHubClient,
    secrets: dict[str, str] | None = None,
    redis_client=None,
) -> None:
    global _client, _hmac, _guard, _redact
    _client = client
    _hmac = HMACAuth(secrets or {})
    _guard = IdempotencyGuard(redis_client)
    _redact = RedactionLayer(enabled=True)


# ── Schemas ────────────────────────────────────────────────────────────────

class LogEvent(BaseModel):
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    source_system: str = Field(
        ...,
        pattern=r"^(windows_event|linux_syslog|cloud\.\w+|customer\.\w+)$",
    )
    source_host: str = Field("", description="FQDN or hostname")
    event_id: str = Field("", description="Source-native event ID")
    category: str = Field(
        "",
        description="authentication | network | process | audit | application",
    )
    severity: str = Field("informational", pattern=r"^(informational|low|medium|high|critical)$")
    payload: dict[str, Any] = Field(default_factory=dict, description="Source-native payload")
    raw_bytes: str | None = Field(None, description="Raw log line (syslog/CEF passthrough)")
    tags: list[str] = Field(default_factory=list)


class IngestResponse(BaseModel):
    status: str
    event_id: str
    topic: str
    size_bytes: int
    idempotent: bool = False


# ── Dependencies ───────────────────────────────────────────────────────────

async def verify_hmac(
    request: Request,
    x_magenta_signature: str = Header("", alias="X-Magenta-Signature"),
    x_magenta_key: str = Header("", alias="X-Magenta-Key"),
) -> None:
    if not _hmac:
        return
    body = await request.body()
    if x_magenta_signature and x_magenta_key:
        if not _hmac.verify(body, x_magenta_signature, x_magenta_key):
            raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    elif _hmac._secrets:
        raise HTTPException(status_code=401, detail="Missing HMAC signature headers")


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/v1/logs", response_model=IngestResponse)
async def ingest_log(
    event: LogEvent,
    request: Request,
    _auth=Depends(verify_hmac),
) -> IngestResponse:
    """Ingest a single log event into the security automation bus.

    Publishes to the ``raw-logs`` Event Hubs topic.
    Supports HMAC-SHA256 auth via ``X-Magenta-Signature`` header.
    """
    if not _client:
        raise HTTPException(status_code=503, detail="Ingest client not initialized")

    event_id = event.event_id or _make_event_id(event)
    idempotency_key = _make_idempotency_key(event, event_id)

    if _guard:
        duplicate = await _guard.is_duplicate(idempotency_key)
        if duplicate:
            return IngestResponse(
                status="skipped",
                event_id=event_id,
                topic="raw-logs",
                size_bytes=0,
                idempotent=True,
            )

    message = _build_envelope(event, event_id, idempotency_key)

    if _redact:
        message["payload"] = _redact_log_payload(message["payload"])

    try:
        result = await _client.send("raw-logs", message)
    except IntegrationError:
        logger.exception("Failed to publish log event=%s", event_id)
        raise HTTPException(status_code=502, detail="Event Hubs publish failed")

    return IngestResponse(
        status="accepted",
        event_id=event_id,
        topic="raw-logs",
        size_bytes=result.get("size_bytes", 0),
    )


@router.post("/v1/events", response_model=IngestResponse)
async def ingest_raw_event(
    request: Request,
    _auth=Depends(verify_hmac),
) -> IngestResponse:
    """Ingest a raw event body (syslog line, CEF, JSON blob).

    Accepts ``text/plain`` or ``application/octet-stream`` content types.
    The raw bytes are published directly to ``raw-logs`` without schema
    validation (passthrough mode).
    """
    if not _client:
        raise HTTPException(status_code=503, detail="Ingest client not initialized")

    body = await request.body()
    content_type = request.headers.get("content-type", "application/octet-stream")
    source_host = request.headers.get("x-source-host", "unknown")
    source_system = request.headers.get("x-source-system", "customer.custom")

    raw_id = hashlib.sha256(body).hexdigest()[:16]
    idempotency_key = f"{source_system}|{source_host}|{raw_id}"

    if _guard:
        duplicate = await _guard.is_duplicate(idempotency_key, ttl=3600)
        if duplicate:
            return IngestResponse(
                status="skipped", event_id=raw_id, topic="raw-logs",
                size_bytes=0, idempotent=True,
            )

    try:
        result = await _client.send_raw("raw-logs", body, content_type=content_type)
    except IntegrationError:
        logger.exception("Failed to publish raw event")
        raise HTTPException(status_code=502, detail="Event Hubs publish failed")

    return IngestResponse(
        status="accepted",
        event_id=raw_id,
        topic="raw-logs",
        size_bytes=result.get("size_bytes", 0),
    )


@router.get("/v1/health")
async def ingest_health() -> dict:
    """Ingest endpoint health."""
    healthy = _client is not None
    return {
        "status": "healthy" if healthy else "unavailable",
        "client_ready": healthy,
        "hmac_enabled": bool(_hmac and _hmac._secrets),
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_event_id(event: LogEvent) -> str:
    raw = f"{event.source_system}|{event.source_host}|{event.timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _make_idempotency_key(event: LogEvent, event_id: str) -> str:
    return hashlib.sha256(
        f"{event.source_system}|{event.timestamp}|{event.source_host}|{event_id}".encode()
    ).hexdigest()


def _build_envelope(event: LogEvent, event_id: str, idempotency_key: str) -> dict:
    return {
        "schema_version": "1.0",
        "event_type": "security.event",
        "event_id": event_id,
        "correlation_id": hashlib.sha256(
            f"{event.source_system}|{event.source_host}".encode()
        ).hexdigest()[:16],
        "idempotency_key": idempotency_key,
        "source_system": event.source_system,
        "source_host": event.source_host,
        "timestamp": event.timestamp,
        "severity": event.severity,
        "category": event.category,
        "payload": event.payload,
        "tags": event.tags + [f"ingested:{datetime.now(UTC).isoformat()}"],
        "provenance": {
            "pipeline_step": "ingest",
            "input_hash": hashlib.sha256(
                json.dumps(event.payload, sort_keys=True, default=str).encode()
            ).hexdigest()[:16],
        },
    }


def _redact_log_payload(payload: dict) -> dict:
    """Apply PII redaction to log payload fields."""
    import copy
    redacted = copy.deepcopy(payload)
    sensitive_keys = {"username", "user", "email", "ipaddress", "ip_address", "hostname"}
    for key in redacted:
        if key.lower() in sensitive_keys and isinstance(redacted[key], str):
            redacted[key] = "[REDACTED]"
    return redacted
