"""OpenTelemetry setup — traces, metrics, logs to Azure Monitor / OTLP."""

from __future__ import annotations

import logging

try:
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    trace = None
    metrics = None
    TracerProvider = None
    MeterProvider = None

try:
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
    _AZURE_EXPORTER_AVAILABLE = True
except ImportError:
    _AZURE_EXPORTER_AVAILABLE = False

from magenta.config import settings

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None
_initialized = False


def setup_telemetry(app=None) -> None:
    """Initialize OpenTelemetry tracing and metrics.

    Args:
        app: Optional FastAPI app to instrument.
    """
    global _tracer_provider, _meter_provider, _initialized

    if _initialized:
        logger.debug("Telemetry already initialized, skipping")
        return

    if not settings.telemetry.enabled:
        logger.info("Telemetry disabled via config")
        _initialized = True
        return

    if not _OTEL_AVAILABLE:
        logger.warning("opentelemetry packages not installed — telemetry disabled. "
                       "Install with: pip install opentelemetry-sdk opentelemetry-exporter-otlp")
        _initialized = True
        return

    # Determine TLS config from environment
    use_tls = settings.telemetry.use_tls
    insecure = not use_tls

    # Sampling rate at provider creation (not after)
    sampler = TraceIdRatioBased(settings.telemetry.sampling_rate)
    _tracer_provider = TracerProvider(sampler=sampler)
    trace.set_tracer_provider(_tracer_provider)

    # Span exporters
    if settings.telemetry.connection_string and _AZURE_EXPORTER_AVAILABLE:
        azure_exporter = AzureMonitorTraceExporter(
            connection_string=settings.telemetry.connection_string
        )
        _tracer_provider.add_span_processor(BatchSpanProcessor(azure_exporter))
        logger.info("Azure Monitor trace exporter configured")

    # OTLP exporter (Tempo/Jaeger/etc)
    try:
        otlp_trace_exporter = OTLPSpanExporter(
            endpoint=settings.telemetry.otlp_endpoint,
            insecure=insecure,
        )
        _tracer_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
        logger.info(f"OTLP trace exporter configured: {settings.telemetry.otlp_endpoint} (tls={use_tls})")
    except Exception as exc:
        logger.warning(f"Failed to configure OTLP trace exporter: {exc}")

    # Metrics provider
    try:
        otlp_metric_exporter = OTLPMetricExporter(
            endpoint=settings.telemetry.otlp_endpoint,
            insecure=insecure,
        )
        metric_reader = PeriodicExportingMetricReader(
            exporter=otlp_metric_exporter,
            export_interval_millis=30000,
        )
        _meter_provider = MeterProvider(metric_readers=[metric_reader])
        metrics.set_meter_provider(_meter_provider)
        logger.info("OTLP metric exporter configured")
    except Exception as exc:
        logger.warning(f"Failed to configure OTLP metric exporter: {exc}")

    # Auto-instrumentation
    if app:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumentation enabled")

    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument(engine=None)

    logger.info(f"Trace sampling rate: {settings.telemetry.sampling_rate}")
    _initialized = True


def get_tracer(name: str = "magenta") -> trace.Tracer:
    """Get a tracer instance."""
    if not _OTEL_AVAILABLE or trace is None:
        return _NoOpTracer()
    return trace.get_tracer(name)


def get_meter(name: str = "magenta") -> metrics.Meter:
    """Get a meter instance."""
    if not _OTEL_AVAILABLE or metrics is None:
        return _NoOpMeter()
    return metrics.get_meter(name)


def shutdown_telemetry() -> None:
    """Shutdown telemetry providers gracefully."""
    global _tracer_provider, _meter_provider
    if _tracer_provider:
        _tracer_provider.shutdown()
    if _meter_provider:
        _meter_provider.shutdown()
    logger.info("Telemetry shutdown complete")


class _NoOpTracer:
    """No-op tracer when OTel is unavailable."""
    from contextlib import contextmanager

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs):
        yield _NoOpSpan()


class _NoOpSpan:
    """No-op span when OTel is unavailable."""
    def set_status(self, *args, **kwargs): pass
    def set_attribute(self, *args, **kwargs): pass
    def add_event(self, *args, **kwargs): pass


class _NoOpMeter:
    """No-op meter when OTel is unavailable."""
    def create_histogram(self, *args, **kwargs): return _NoOpHistogram()
    def create_counter(self, *args, **kwargs): return _NoOpCounter()


class _NoOpHistogram:
    def record(self, *args, **kwargs): pass


class _NoOpCounter:
    def add(self, *args, **kwargs): pass
