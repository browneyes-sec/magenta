"""Custom scenario loader — loads user-defined scenarios from TOML config."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from chaos_engineering.attestation.preparing import ComponentMap
from chaos_engineering.chaos import ScenarioResult

logger = logging.getLogger(__name__)


def load_custom_scenario(config: dict) -> type | None:
    """Load a custom scenario class from TOML config.

    Config should specify:
        module = "path/to/custom.py"
        class_name = "MyCustomScenario"
    """
    module_path = config.get("module", "")
    class_name = config.get("class_name", "")

    if not module_path or not class_name:
        logger.warning("Custom scenario config missing module or class_name")
        return None

    path = Path(module_path)
    if not path.exists():
        logger.warning("Custom scenario module not found: %s", module_path)
        return None

    try:
        spec = importlib.util.spec_from_file_location(
            f"chaos_engineering.scenarios.custom_{class_name}", path
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        cls = getattr(mod, class_name, None)
        if cls is None:
            logger.warning("Class %s not found in %s", class_name, module_path)
            return None

        return cls

    except Exception as exc:
        logger.warning("Failed to load custom scenario: %s", exc)
        return None


class CustomScenario:
    """Placeholder for user-defined scenarios. See readme.md for configuration."""

    name = "custom"
    description = "User-defined scenario"
    severity = "low"
    dtp_reference = "Custom"

    def __init__(self, intensity: int = 1):
        self.intensity = intensity

    def check_components(self, components: ComponentMap) -> tuple[bool, str]:
        return True, ""

    def run(self, components: ComponentMap, stealth: bool) -> ScenarioResult:
        return ScenarioResult(
            scenario=self.name,
            status="skipped",
            reason="Custom scenario not configured. See chaos.toml [scenarios.custom]",
        )

    def validate(self, components: ComponentMap) -> list[dict]:
        return []

    def recommend(self) -> dict:
        return {"short_term": [], "long_term": []}
