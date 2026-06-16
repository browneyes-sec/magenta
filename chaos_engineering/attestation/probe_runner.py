"""Probe runner — executes existing magnet/probes/ and returns results."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any

from chaos_engineering.attestation.preparing import ComponentMap

logger = logging.getLogger(__name__)


class ProbeRunner:
    """Runs probes from magnet/probes/ against the live framework."""

    def __init__(self, components: ComponentMap):
        self._components = components
        self._probes_dir = Path("magnet/probes")

    def run_all(self) -> list[dict[str, Any]]:
        """Discover and run all available probes."""
        results = []
        available = self._components.probes

        if not available:
            logger.info("No probes available — skipping probe run")
            return results

        for name in available:
            result = self._run_probe(name)
            results.append(result)

        return results

    def run(self, name: str) -> dict[str, Any]:
        """Run a specific probe by name."""
        return self._run_probe(name)

    def _run_probe(self, name: str) -> dict[str, Any]:
        """Load and execute a single probe."""
        probe_path = self._probes_dir / f"{name}_probe.py"

        if not probe_path.exists():
            return {
                "probe": name,
                "healthy": False,
                "status": "error",
                "error": f"Probe file not found: {probe_path}",
            }

        try:
            spec = importlib.util.spec_from_file_location(
                f"magnet.probes.{name}_probe", probe_path
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if hasattr(mod, "run"):
                result = mod.run()
                healthy = result.get("healthy", True) if isinstance(result, dict) else True
                return {
                    "probe": name,
                    "healthy": healthy,
                    "status": "completed",
                    "result": result,
                }
            return {
                "probe": name,
                "healthy": False,
                "status": "error",
                "error": "Probe has no run() function",
            }
        except Exception as exc:
            logger.warning("Probe %s failed: %s", name, exc)
            return {
                "probe": name,
                "healthy": False,
                "status": "error",
                "error": str(exc),
            }
