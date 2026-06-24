"""Structured JSON logging for all Magenta components."""

import json
import logging
from datetime import datetime


class StructuredFormatter(logging.Formatter):
    """JSON formatter with required fields for Magenta."""

    REQUIRED_FIELDS = [
        "mission_id",
        "agent_id",
        "correlation_id",
        "action",
        "risk_score",
        "model",
        "latency_ms",
        "status",
    ]

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "magenta",
        }

        # Attach structured context if present
        for field in self.REQUIRED_FIELDS:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)

        # Include any extra fields not in REQUIRED_FIELDS
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "thread", "threadName",
                "exc_info", "exc_text", "stack_info", "getMessage",
            }:
                if key not in log_entry:
                    log_entry[key] = value

        # Include exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def get_structured_logger(name: str) -> logging.Logger:
    """Get a logger configured with StructuredFormatter.

    Uses propagation to root handler — avoids duplicating handlers.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    # Do NOT add handlers here — rely on root logger via propagation
    logger.propagate = True
    return logger


class StructuredLogger:
    """Wrapper for structured logging with mission/agent context.

    Uses __slots__ for memory efficiency. bind() mutates in-place
    instead of creating new instances.
    """

    __slots__ = ("_logger", "mission_id", "agent_id", "correlation_id")

    def __init__(
        self,
        logger: logging.Logger,
        mission_id: str | None = None,
        agent_id: str | None = None,
        correlation_id: str | None = None,
    ):
        self._logger = logger
        self.mission_id = mission_id
        self.agent_id = agent_id
        self.correlation_id = correlation_id

    def _log(self, level: int, message: str, **extra) -> None:
        merged = {}
        if self.mission_id:
            merged["mission_id"] = self.mission_id
        if self.agent_id:
            merged["agent_id"] = self.agent_id
        if self.correlation_id:
            merged["correlation_id"] = self.correlation_id
        merged.update(extra)
        self._logger.log(level, message, extra=merged)

    def info(self, message: str, **extra) -> None:
        self._log(logging.INFO, message, **extra)

    def warning(self, message: str, **extra) -> None:
        self._log(logging.WARNING, message, **extra)

    def error(self, message: str, **extra) -> None:
        self._log(logging.ERROR, message, **extra)

    def debug(self, message: str, **extra) -> None:
        self._log(logging.DEBUG, message, **extra)

    def critical(self, message: str, **extra) -> None:
        self._log(logging.CRITICAL, message, **extra)

    def bind(self, **extra) -> "StructuredLogger":
        """Bind additional context in-place (mutates self, returns self for chaining)."""
        for key in ("mission_id", "agent_id", "correlation_id"):
            if key in extra:
                setattr(self, key, extra[key])
        return self


def setup_structured_logging(level: int = logging.INFO, json_format: bool = True) -> None:
    """Configure root logger with structured formatting."""
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler()
    if json_format:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
    root.addHandler(handler)

    # Reduce noise from third-party loggers
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)
