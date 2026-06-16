"""Registry poison scenario — inject malformed agent configs into registry."""

from __future__ import annotations

import time
from typing import Any

from chaos_engineering.attestation.preparing import ComponentMap
from chaos_engineering.chaos import ScenarioResult
from chaos_engineering.injection.registry_injector import RegistryInjector


class RegistryPoisonScenario:
    """Inject malformed agent configs and validate registry rejection."""

    name = "registry_poison"
    description = "Injects malformed agent configs to test registry validation"
    severity = "high"
    dtp_reference = "DTP-03 §5.3 Scenario 5"

    def __init__(self, intensity: int = 1):
        self.intensity = intensity
        self.injector = RegistryInjector()

    def check_components(self, components: ComponentMap) -> tuple[bool, str]:
        if not components.registry_writable:
            return False, "Agent registry not writable"
        return True, ""

    def run(self, components: ComponentMap, stealth: bool) -> ScenarioResult:
        inject_result = self.injector.inject_poison(
            components, count=self.intensity
        )

        all_rejected = all(
            item.get("rejected", False) for item in inject_result.get("injected", [])
        )

        return ScenarioResult(
            scenario=self.name,
            status="passed" if all_rejected else "failed",
            injection_details=inject_result,
        )

    def validate(self, components: ComponentMap) -> list[dict]:
        from chaos_engineering.attestation.probe_runner import ProbeRunner
        runner = ProbeRunner(components)
        return runner.run_all()

    def recommend(self) -> dict:
        return {
            "short_term": [
                "Verify registry rejects all malformed configs",
                "Check no poison entries persisted in registry state",
                "Validate error logging captured for audit trail",
            ],
            "long_term": [
                "Implement AgentConfig schema validation on registration",
                "Add registry integrity check on startup",
                "Consider allowlist for agent registration sources",
            ],
        }
