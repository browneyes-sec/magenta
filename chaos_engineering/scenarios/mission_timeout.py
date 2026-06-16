"""Mission timeout scenario — mission exceeds SLA deadline."""

from __future__ import annotations

import time
from typing import Any

from chaos_engineering.attestation.preparing import ComponentMap
from chaos_engineering.chaos import ScenarioResult
from chaos_engineering.injection.mission_injector import MissionInjector


class MissionTimeoutScenario:
    """Set mission deadlines to the past to trigger timeout escalation."""

    name = "mission_timeout"
    description = "Sets mission deadlines to past to trigger timeout"
    severity = "low"
    dtp_reference = "DTP-03 §5.3 Scenario 4"

    def __init__(self, intensity: int = 1):
        self.intensity = intensity
        self.injector = MissionInjector()

    def check_components(self, components: ComponentMap) -> tuple[bool, str]:
        if not components.mission_manager:
            return False, "Mission manager not available"
        return True, ""

    def run(self, components: ComponentMap, stealth: bool) -> ScenarioResult:
        inject_result = self.injector.set_expired_deadline(
            components, count=self.intensity
        )

        return ScenarioResult(
            scenario=self.name,
            status="passed" if inject_result["count"] > 0 else "skipped",
            reason=inject_result.get("reason", ""),
            injection_details=inject_result,
        )

    def validate(self, components: ComponentMap) -> list[dict]:
        from chaos_engineering.attestation.probe_runner import ProbeRunner
        runner = ProbeRunner(components)
        return runner.run_all()

    def recommend(self) -> dict:
        return {
            "short_term": [
                "Verify timeout detection triggers within 30s",
                "Check mission status set to 'escalated' on timeout",
                "Validate SOC notification sent for timed-out missions",
            ],
            "long_term": [
                "Implement configurable timeout per severity level",
                "Add automatic escalation chain for timed-out missions",
                "Consider mission deadline extension API for operators",
            ],
        }
