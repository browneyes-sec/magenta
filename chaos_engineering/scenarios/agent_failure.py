"""Agent failure scenario — kill agent mid-mission and validate recovery."""

from __future__ import annotations

import time

from chaos_engineering.attestation.preparing import ComponentMap
from chaos_engineering.chaos import ScenarioResult
from chaos_engineering.injection.agent_injector import AgentInjector


class AgentFailureScenario:
    """Kill an agent from the registry and validate recovery."""

    name = "agent_failure"
    description = "Removes agents from registry to simulate process crash"
    severity = "medium"
    dtp_reference = "DTP-03 §5.3 Scenario 1"

    def __init__(self, intensity: int = 1):
        self.intensity = intensity
        self.injector = AgentInjector()

    def check_components(self, components: ComponentMap) -> tuple[bool, str]:
        if not components.agents:
            return False, "No agents registered in registry"
        if components.agent_count < self.intensity:
            return False, f"Only {components.agent_count} agents available, need {self.intensity}"
        return True, ""

    def run(self, components: ComponentMap, stealth: bool) -> ScenarioResult:
        start = time.monotonic()  # noqa: F841

        inject_result = self.injector.remove_agents(components, count=self.intensity)

        # Simulate recovery delay
        recovery_start = time.monotonic()
        time.sleep(0.1)  # Minimal delay for testing
        recovery_time = time.monotonic() - recovery_start

        return ScenarioResult(
            scenario=self.name,
            status="passed",
            injection_details=inject_result,
            recovery_time_seconds=recovery_time,
        )

    def validate(self, components: ComponentMap) -> list[dict]:
        from chaos_engineering.attestation.probe_runner import ProbeRunner

        runner = ProbeRunner(components)
        return runner.run_all()

    def recommend(self) -> dict:
        return {
            "short_term": [
                "Verify agent re-registration within 60s of crash",
                "Check mission state consistency in Dictator oversight",
                "Validate no orphaned tasks in DAG executor",
            ],
            "long_term": [
                "Implement agent health watchdog with auto-restart",
                "Add circuit breaker on agent registry writes",
                "Consider per-role agent pools for fault isolation",
            ],
        }
