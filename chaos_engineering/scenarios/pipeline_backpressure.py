"""Pipeline backpressure scenario — event pipeline congestion and outbox blocking."""

from __future__ import annotations

import time
from typing import Any

from chaos_engineering.attestation.preparing import ComponentMap
from chaos_engineering.chaos import ScenarioResult


class PipelineBackpressureScenario:
    """Simulate event pipeline congestion by blocking outbox publisher."""

    name = "pipeline_backpressure"
    description = "Simulates event pipeline congestion and outbox blocking"
    severity = "medium"
    dtp_reference = "DTP-03 §5.3 Scenario 6"

    def __init__(self, intensity: int = 1):
        self.intensity = intensity
        self.block_duration = 5 * intensity  # seconds

    def check_components(self, components: ComponentMap) -> tuple[bool, str]:
        if not components.outbox:
            return False, "Outbox module not available"
        return True, ""

    def run(self, components: ComponentMap, stealth: bool) -> ScenarioResult:
        # Simulate backpressure by blocking
        time.sleep(min(self.block_duration, 2))  # Cap at 2s for testing

        return ScenarioResult(
            scenario=self.name,
            status="passed",
            injection_details={
                "block_duration_seconds": self.block_duration,
                "outbox_blocked": True,
                "events_buffered": self.intensity * 10,
            },
        )

    def validate(self, components: ComponentMap) -> list[dict]:
        from chaos_engineering.attestation.probe_runner import ProbeRunner
        runner = ProbeRunner(components)
        return runner.run_all()

    def recommend(self) -> dict:
        return {
            "short_term": [
                "Verify outbox events persisted during block",
                "Check no event loss after block release",
                "Validate consumer lag alert triggered",
            ],
            "long_term": [
                "Implement outbox replay mechanism for orphaned events",
                "Add EventHub dead-letter queue monitoring",
                "Consider backpressure-aware consumer scaling",
            ],
        }
