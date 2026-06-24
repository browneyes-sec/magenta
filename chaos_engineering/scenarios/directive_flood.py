"""Directive flood scenario — overwhelm Dictator with rapid-fire directives."""

from __future__ import annotations

from chaos_engineering.attestation.preparing import ComponentMap
from chaos_engineering.chaos import ScenarioResult
from chaos_engineering.injection.directive_injector import DirectiveInjector


class DirectiveFloodScenario:
    """Flood the Dictator with rapid-fire directives."""

    name = "directive_flood"
    description = "Issues rapid-fire directives to overwhelm the Dictator"
    severity = "high"
    dtp_reference = "DTP-03 §5.3 Scenario 2"

    def __init__(self, intensity: int = 1):
        self.intensity = intensity
        self.injector = DirectiveInjector()
        self.flood_count = 100 * intensity
        self.flood_interval_ms = max(10, 100 // intensity)

    def check_components(self, components: ComponentMap) -> tuple[bool, str]:
        if not components.dictator:
            return False, "Dictator agent not available"
        return True, ""

    def run(self, components: ComponentMap, stealth: bool) -> ScenarioResult:
        inject_result = self.injector.flood_directives(
            components,
            count=self.flood_count,
            interval_ms=self.flood_interval_ms,
        )

        return ScenarioResult(
            scenario=self.name,
            status="passed" if inject_result["errors"] == 0 else "failed",
            injection_details=inject_result,
            recovery_time_seconds=0.0,
        )

    def validate(self, components: ComponentMap) -> list[dict]:
        from chaos_engineering.attestation.probe_runner import ProbeRunner

        runner = ProbeRunner(components)
        return runner.run_all()

    def recommend(self) -> dict:
        return {
            "short_term": [
                "Verify directive log integrity after flood",
                "Check Dictator state returned to idle",
                "Validate no duplicate directives executed",
            ],
            "long_term": [
                "Implement directive rate limiting per source",
                "Add directive deduplication in Dictator state",
                "Consider directive priority queue with backpressure",
            ],
        }
