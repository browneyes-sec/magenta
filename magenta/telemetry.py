"""OpenTelemetry setup — traces, metrics, logs to Azure Monitor / OTLP."""

from __future__ import annotations

import logging
from typing import Optional

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

from magenta.config import settings

logger = logging.getLogger(__name__)

_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None


def setup_telemetry(app=None) -> None:
    """Initialize OpenTelemetry tracing and metrics.

    Args:
        app: Optional FastAPI app to instrument.
    """
    global _tracer_provider, _meter_provider

    if not settings.telemetry.enabled:
        logger.info("Telemetry disabled via config")
        return

    # Trace provider
    _tracer_provider = TracerProvider()
    trace.set_tracer_provider(_tracer_provider)

    # Span exporters
    if settings.telemetry.connection_string:
        azure_exporter = AzureMonitorTraceExporter(
            connection_string=settings.telemetry.connection_string
        )
        _tracer_provider.add_span_processor(BatchSpanProcessor(azure_exporter))
        logger.info("Azure Monitor trace exporter configured")

    # OTLP exporter (Tempo/Jaeger/etc)
    otlp_trace_exporter = OTLPSpanExporter(
        endpoint=settings.telemetry.otlp_endpoint,
        insecure=True,
    )
    _tracer_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
    logger.info(f"OTLP trace exporter configured: {settings.telemetry.otlp_endpoint}")

    # Metrics provider
    otlp_metric_exporter = OTLPMetricExporter(
        endpoint=settings.telemetry.otlp_endpoint,
        insecure=True,
    )
    metric_reader = PeriodicExportingMetricReader(
        exporter=otlp_metric_exporter,
        export_interval_millis=30000,
    )
    _meter_provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(_meter_provider)
    logger.info("OTLP metric exporter configured")

    # Auto-instrumentation
    if app:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumentation enabled")

    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument(engine=None)  # Will instrument on engine creation

    # Set sampling rate
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    _tracer_provider.sampler = TraceIdRatioBased(settings.telemetry.sampling_rate)
    logger.info(f"Trace sampling rate: {settings.telemetry.sampling_rate}")


def get_tracer(name: str = "magenta") -> trace.Tracer:
    """Get a tracer instance."""
    return trace.get_tracer(name)


def get_meter(name: str = "magenta") -> metrics.Meter:
    """Get a meter instance."""
    return metrics.get_meter(name)


def shutdown_telemetry() -> None:
    """Shutdown telemetry providers gracefully."""
    global _tracer_provider, _meter_provider
    if _tracer_provider:
        _tracer_provider.shutdown()
    if _meter_provider:
        _meter_provider.shutdown()
    logger.info("Telemetry shutdown complete")