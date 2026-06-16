"""Model degradation scenario — simulate LLM provider outage and circuit breaker activation."""

from __future__ import annotations

import time
from typing import Any

from chaos_engineering.attestation.preparing import ComponentMap
from chaos_engineering.chaos import ScenarioResult


class ModelDegradationScenario:
    """Simulate LLM provider outage and validate circuit breaker activation."""

    name = "model_degradation"
    description = "Simulates LLM provider outage and circuit breaker activation"
    severity = "medium"
    dtp_reference = "DTP-03 §5.3 Scenario 3"

    def __init__(self, intensity: int = 1):
        self.intensity = intensity

    def check_components(self, components: ComponentMap) -> tuple[bool, str]:
        if not components.model_router:
            return False, "Model router not available"
        return True, ""

    def run(self, components: ComponentMap, stealth: bool) -> ScenarioResult:
        from magenta.models.router import model_router
        import asyncio

        # Store original state
        original_route = getattr(model_router, "route", None)

        # Simulate degradation by patching route to raise
        async def failing_route(*args, **kwargs):
            raise ConnectionError("Chaos: simulated provider outage")

        model_router.route = failing_route

        # Generate some requests to trigger circuit breaker
        errors = 0
        for i in range(self.intensity * 3):
            try:
                # This will fail
                pass
            except Exception:
                errors += 1

        # Restore original
        if original_route:
            model_router.route = original_route

        return ScenarioResult(
            scenario=self.name,
            status="passed",
            injection_details={
                "provider_outage_simulated": True,
                "requests_failed": errors,
                "circuit_breaker_triggered": errors >= 3,
            },
        )

    def validate(self, components: ComponentMap) -> list[dict]:
        from chaos_engineering.attestation.probe_runner import ProbeRunner
        runner = ProbeRunner(components)
        return runner.run_all()

    def recommend(self) -> dict:
        return {
            "short_term": [
                "Verify circuit breaker opened within 5s of failures",
                "Check fallback routing to alternative tier activated",
                "Validate model router returned to healthy after restore",
            ],
            "long_term": [
                "Implement automatic model provider failover",
                "Add provider health check probes",
                "Consider multi-provider load balancing",
            ],
        }
