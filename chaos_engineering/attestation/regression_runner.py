"""Regression runner — executes magnet/ test suite with fallback to lightweight subset."""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Any

from chaos_engineering.attestation.preparing import ComponentMap

logger = logging.getLogger(__name__)


class RegressionRunner:
    """Runs the magnet/ regression suite with automatic fallback."""

    def __init__(self, components: ComponentMap):
        self._components = components
        self._mode = components.regression  # full | lightweight | none

    def run(self) -> dict[str, Any]:
        """Run regression suite based on available components."""
        if self._mode == "none":
            logger.info("No test suite available — skipping regression")
            return {
                "status": "skipped",
                "reason": "No magnet/ test suite found",
                "mode": "none",
                "total": 0,
                "passed": 0,
                "failed": 0,
            }

        if self._mode == "full":
            return self._run_full()
        else:
            return self._run_lightweight()

    def _run_full(self) -> dict[str, Any]:
        """Run the full magnet/ test suite."""
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "magnet/",
            "-q",
            "--tb=short",
            "--no-header",
        ]
        return self._execute(cmd, mode="full")

    def _run_lightweight(self) -> dict[str, Any]:
        """Run core + agent tests only (no external deps)."""
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "magnet/test_core/",
            "magnet/test_agents/",
            "-q",
            "--tb=short",
            "--no-header",
        ]
        return self._execute(cmd, mode="lightweight")

    def _execute(self, cmd: list[str], mode: str) -> dict[str, Any]:
        """Execute pytest command and parse results."""
        logger.info("Running regression: %s (mode=%s)", " ".join(cmd), mode)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            output = result.stdout + result.stderr
            passed, failed, total = self._parse_results(output)

            return {
                "status": "completed" if result.returncode == 0 else "failed",
                "mode": mode,
                "total": total,
                "passed": passed,
                "failed": failed,
                "exit_code": result.returncode,
                "output": output[-2000:] if len(output) > 2000 else output,
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "mode": mode,
                "reason": "Regression timed out after 300s",
                "total": 0,
                "passed": 0,
                "failed": 0,
            }
        except Exception as exc:
            return {
                "status": "error",
                "mode": mode,
                "reason": str(exc),
                "total": 0,
                "passed": 0,
                "failed": 0,
            }

    def _parse_results(self, output: str) -> tuple[int, int, int]:
        """Parse pytest output for pass/fail counts."""
        passed = 0
        failed = 0
        total = 0

        for line in output.split("\n"):
            line = line.strip()
            if "passed" in line and "failed" in line:
                # e.g. "24 passed, 2 failed in 5.12s"
                parts = line.split(",")
                for part in parts:
                    part = part.strip()
                    if "passed" in part:
                        passed = int(part.split()[0])
                    elif "failed" in part:
                        failed = int(part.split()[0])
                total = passed + failed
            elif line.endswith("passed") and "failed" not in line:
                # e.g. "24 passed in 5.12s"
                passed = int(line.split()[0])
                total = passed
            elif "failed" in line and "passed" not in line:
                # e.g. "2 failed in 5.12s"
                failed = int(line.split()[0])
                total = failed

        return passed, failed, total
