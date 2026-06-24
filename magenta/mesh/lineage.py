"""OpenLineage Integration — data lineage tracking for Magenta pipelines.

Emits OpenLineage events for data flow tracking across collectors,
normalizers, enrichment, and storage. Compatible with OpenLineage
backends (Marquez, DataHub, etc.).

DTP §E2: OpenLineage Integration.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace

    _tracer = trace.get_tracer("magenta.lineage")
except Exception:
    _tracer = None


class LineageEvent:
    """OpenLineage-compliant lineage event.

    Follows the OpenLineage spec:
    https://openlineage.io/docs/spec/event/
    """

    def __init__(
        self,
        event_type: str,
        run_id: str,
        job_name: str,
        job_namespace: str = "magenta",
    ):
        self.event_type = event_type
        self.run_id = run_id
        self.job_name = job_name
        self.job_namespace = job_namespace
        self.event_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.event_id = str(uuid4())
        self.inputs: list[dict[str, Any]] = []
        self.outputs: list[dict[str, Any]] = []
        self.facets: dict[str, Any] = {}

    def add_input(self, name: str, namespace: str = "magenta", **kwargs: Any) -> None:
        self.inputs.append(
            {
                "name": name,
                "namespace": namespace,
                **kwargs,
            }
        )

    def add_output(self, name: str, namespace: str = "magenta", **kwargs: Any) -> None:
        self.outputs.append(
            {
                "name": name,
                "namespace": namespace,
                **kwargs,
            }
        )

    def add_facet(self, name: str, facet: dict[str, Any]) -> None:
        self.facets[name] = facet

    def to_dict(self) -> dict[str, Any]:
        return {
            "eventType": self.event_type,
            "eventTime": self.event_time,
            "run": {
                "runId": self.run_id,
                "facets": self.facets.get("run", {}),
            },
            "job": {
                "namespace": self.job_namespace,
                "name": self.job_name,
                "facets": self.facets.get("job", {}),
            },
            "inputs": self.inputs,
            "outputs": self.outputs,
            "schemaURL": "https://openlineage.io/spec/1-0-5/OpenLineage.json",
        }


class LineageTracker:
    """Tracks data lineage across Magenta pipelines.

    Emits START, COMPLETE, and FAIL events for each pipeline step.
    Tracks provenance from ingestion through normalization, enrichment,
    and storage.
    """

    def __init__(self):
        self._runs: dict[str, dict[str, Any]] = {}

    def start_run(
        self,
        job_name: str,
        run_id: str | None = None,
        inputs: list[dict[str, Any]] | None = None,
    ) -> str:
        """Start a new lineage run. Returns the run_id."""
        run_id = run_id or str(uuid4())
        event = LineageEvent("START", run_id, job_name)

        for inp in inputs or []:
            event.add_input(**inp)

        self._runs[run_id] = {
            "job_name": job_name,
            "start_time": time.time(),
            "inputs": event.inputs.copy(),
            "outputs": [],
            "status": "running",
        }

        self._emit(event)
        return run_id

    def complete_run(
        self,
        run_id: str,
        outputs: list[dict[str, Any]] | None = None,
        facets: dict[str, Any] | None = None,
    ) -> None:
        """Complete a lineage run with output datasets."""
        run_info = self._runs.get(run_id)
        if not run_info:
            logger.warning("Unknown run_id=%s for complete_run", run_id)
            return

        event = LineageEvent("COMPLETE", run_id, run_info["job_name"])

        for inp in run_info["inputs"]:
            event.add_input(**inp)

        for out in outputs or []:
            event.add_output(**out)
            run_info["outputs"].append(out)

        if facets:
            for name, facet in facets.items():
                event.add_facet(name, facet)

        duration_ms = (time.time() - run_info["start_time"]) * 1000
        event.add_facet("run", {"durationMs": round(duration_ms, 2)})

        run_info["status"] = "completed"
        self._emit(event)

    def fail_run(
        self,
        run_id: str,
        error: str = "",
        facets: dict[str, Any] | None = None,
    ) -> None:
        """Mark a lineage run as failed."""
        run_info = self._runs.get(run_id)
        if not run_info:
            return

        event = LineageEvent("FAIL", run_id, run_info["job_name"])

        for inp in run_info["inputs"]:
            event.add_input(**inp)

        if facets:
            for name, facet in facets.items():
                event.add_facet(name, facet)

        event.add_facet("run", {"errorMessage": error})

        run_info["status"] = "failed"
        self._emit(event)

    def track_envelope(
        self,
        event_id: str,
        source: str,
        destination: str,
        pipeline_step: str,
        correlation_id: str = "",
    ) -> str:
        """Track a single event envelope through the pipeline. Returns run_id."""
        run_id = self.start_run(
            job_name=f"pipeline.{pipeline_step}",
            inputs=[{"name": source, "namespace": "magenta.ingest"}],
        )

        self.complete_run(
            run_id,
            outputs=[{"name": destination, "namespace": "magenta.storage"}],
            facets={
                "magenta": {
                    "eventId": event_id,
                    "correlationId": correlation_id,
                    "pipelineStep": pipeline_step,
                },
            },
        )

        return run_id

    def _emit(self, event: LineageEvent) -> None:
        """Emit a lineage event. Logs locally, emits OTel span if available."""
        logger.debug(
            "Lineage event: type=%s job=%s run=%s inputs=%d outputs=%d",
            event.event_type,
            event.job_name,
            event.run_id,
            len(event.inputs),
            len(event.outputs),
        )

        if _tracer:
            try:
                span = _tracer.start_span(
                    f"lineage.{event.event_type.lower()}",
                    attributes={
                        "lineage.job": event.job_name,
                        "lineage.run_id": event.run_id,
                        "lineage.event_type": event.event_type,
                        "lineage.inputs": len(event.inputs),
                        "lineage.outputs": len(event.outputs),
                    },
                )
                span.end()
            except Exception:
                pass

    def get_run_info(self, run_id: str) -> dict[str, Any] | None:
        return self._runs.get(run_id)

    def list_runs(self, status: str = "") -> list[dict[str, Any]]:
        runs = [
            {
                "run_id": rid,
                "job_name": info["job_name"],
                "status": info["status"],
                "start_time": info["start_time"],
                "inputs": len(info["inputs"]),
                "outputs": len(info["outputs"]),
            }
            for rid, info in self._runs.items()
        ]
        if status:
            runs = [r for r in runs if r["status"] == status]
        return runs


# Module-level singleton
lineage_tracker = LineageTracker()
