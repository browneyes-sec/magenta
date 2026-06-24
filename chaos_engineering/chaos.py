"""Chaos Engineering Engine — 1-click entry point for fault injection and resilience validation.

Usage:
    from chaos_engineering.chaos import ChaosEngine
    engine = ChaosEngine()
    result = engine.run(scenario="agent_failure", intensity=3)
"""

from __future__ import annotations

import json
import logging
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from chaos_engineering.attestation.preparing import ComponentMap, PreparingStage
from chaos_engineering.attestation.probe_runner import ProbeRunner
from chaos_engineering.attestation.regression_runner import RegressionRunner
from chaos_engineering.attestation.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "chaos.toml"


@dataclass
class ScenarioResult:
    """Result of a single chaos scenario execution."""

    scenario: str
    status: str  # passed | failed | skipped | error
    reason: str = ""
    injection_details: dict = field(default_factory=dict)
    recovery_time_seconds: float = 0.0
    probe_results: list = field(default_factory=list)
    recommendations: dict = field(default_factory=dict)


@dataclass
class ChaosRunResult:
    """Complete result of a chaos engineering run."""

    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    intensity: int = 3
    stealth: bool = False
    scenarios_run: int = 0
    scenarios_passed: int = 0
    scenarios_failed: int = 0
    scenarios_skipped: int = 0
    results: list[ScenarioResult] = field(default_factory=list)
    baseline_probes: list = field(default_factory=list)
    post_probes: list = field(default_factory=list)
    regression: dict | None = None
    preparing: dict | None = None
    verdict: str = "pending"


class ChaosEngine:
    """Main orchestrator for chaos engineering runs.

    1-click entry: engine.run() loads config, injects faults, validates, reports.
    """

    def __init__(self, config_path: str | None = None):
        self.config_path = Path(config_path) if config_path else CONFIG_PATH
        self.config = self._load_config()
        self.reports_dir = Path(
            self.config.get("logging", {}).get("log_dir", "chaos_engineering/reports")
        )
        self.cert_dir = Path(
            self.config.get("certification", {}).get("output_dir", "docs/certifications")
        )
        self.run_id = self._generate_run_id()
        self._setup_logging()

    def _load_config(self) -> dict:
        if self.config_path.exists():
            with open(self.config_path, "rb") as f:
                return tomllib.load(f)
        logger.warning("chaos.toml not found at %s, using defaults", self.config_path)
        return {}

    def _generate_run_id(self) -> str:
        now = datetime.utcnow()
        date_str = now.strftime("%d_%m_%y")
        run_dir = self.reports_dir / f"chaos-{date_str}"
        run_dir.mkdir(parents=True, exist_ok=True)
        existing = list(run_dir.glob("run-*.json"))
        run_num = len(existing) + 1
        return f"chaos-{date_str}-{run_num:03d}"

    def _setup_logging(self):
        log_dir = self.reports_dir / self.run_id
        log_dir.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger(f"chaos.{self.run_id}")
        self._logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler(log_dir / "run.log")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        self._logger.addHandler(fh)

        self._stealth_logger = logging.getLogger(f"chaos.stealth.{self.run_id}")
        sh = logging.FileHandler(log_dir / "stealth.log")
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        self._stealth_logger.addHandler(sh)

    def run(
        self,
        scenario: str | None = None,
        intensity: int | None = None,
        stealth: bool | None = None,
        timeout: int | None = None,
        dry_run: bool = False,
        validate: bool = True,
    ) -> ChaosRunResult:
        """Execute a chaos engineering run with auto-validation."""
        defaults = self.config.get("defaults", {})
        intensity = intensity or defaults.get("intensity", 3)
        stealth = stealth if stealth is not None else defaults.get("stealth", False)
        timeout = timeout or defaults.get("timeout", 300)

        result = ChaosRunResult(
            run_id=self.run_id,
            started_at=datetime.utcnow(),
            intensity=intensity,
            stealth=stealth,
        )

        self._logger.info(
            "Chaos run started: %s (intensity=%d, stealth=%s)", self.run_id, intensity, stealth
        )

        # 1. Preparing stage
        preparing = PreparingStage()
        components = preparing.scan()
        result.preparing = components.to_dict()
        self._logger.info("Preparing stage complete: %s", json.dumps(result.preparing, default=str))

        if dry_run:
            self._logger.info("Dry run — no injection will occur")
            result.verdict = "dry_run"
            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
            return result

        # 2. Baseline probe snapshot
        probe_runner = ProbeRunner(components)
        result.baseline_probes = probe_runner.run_all()
        self._logger.info(
            "Baseline probes: %d passed, %d failed",
            sum(1 for p in result.baseline_probes if p.get("healthy")),
            sum(1 for p in result.baseline_probes if not p.get("healthy")),
        )

        # 3. Load and execute scenarios
        scenarios_to_run = self._resolve_scenarios(scenario, components)
        for scenario_cls in scenarios_to_run:
            scenario_result = self._execute_scenario(
                scenario_cls, intensity, stealth, timeout, components
            )
            result.results.append(scenario_result)
            if scenario_result.status == "passed":
                result.scenarios_passed += 1
            elif scenario_result.status == "failed":
                result.scenarios_failed += 1
            elif scenario_result.status == "skipped":
                result.scenarios_skipped += 1
            result.scenarios_run += 1

        # 4. Post-chaos probes
        result.post_probes = probe_runner.run_all()

        # 5. Regression suite
        if defaults.get("auto_validate", True) and validate:
            regression = RegressionRunner(components)
            reg_result = regression.run()
            result.regression = reg_result
            self._logger.info("Regression: %s", json.dumps(reg_result, default=str))

        # 6. Determine verdict
        result.verdict = self._determine_verdict(result)

        # 7. Generate certification
        result.completed_at = datetime.utcnow()
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()

        report_gen = ReportGenerator(self.config)
        report_gen.generate(result, self.run_id)

        self._logger.info(
            "Chaos run completed: verdict=%s, duration=%.1fs",
            result.verdict,
            result.duration_seconds,
        )

        return result

    def _resolve_scenarios(self, scenario: str | None, components: ComponentMap) -> list:
        """Resolve which scenario classes to run."""
        scenarios_config = self.config.get("scenarios", {})

        if scenario and scenario != "all":
            names = [s.strip() for s in scenario.split(",")]
        else:
            names = [
                name
                for name, cfg in scenarios_config.items()
                if cfg.get("enabled", True) and name != "custom"
            ]

        # Load scenario classes
        from chaos_engineering.scenarios import SCENARIO_REGISTRY
        from chaos_engineering.scenarios.custom import load_custom_scenario

        classes = []
        for name in names:
            if name in SCENARIO_REGISTRY:
                classes.append(SCENARIO_REGISTRY[name])
            elif name == "custom" or scenarios_config.get(name, {}).get("module"):
                custom_cls = load_custom_scenario(scenarios_config.get(name, {}))
                if custom_cls:
                    classes.append(custom_cls)
            else:
                self._logger.warning("Unknown scenario: %s (skipping)", name)

        return classes

    def _execute_scenario(
        self,
        scenario_cls,
        intensity: int,
        stealth: bool,
        timeout: int,
        components: ComponentMap,
    ) -> ScenarioResult:
        """Execute a single scenario with timeout and error handling."""
        try:
            instance = scenario_cls(intensity=intensity)

            # Check if scenario is supported by available components
            if hasattr(instance, "check_components"):
                supported, reason = instance.check_components(components)
                if not supported:
                    self._logger.info("Scenario %s skipped: %s", instance.name, reason)
                    return ScenarioResult(
                        scenario=instance.name,
                        status="skipped",
                        reason=reason,
                    )

            # Log injection
            if stealth:
                self._stealth_logger.info("INJECT: %s (intensity=%d)", instance.name, intensity)
            else:
                self._logger.info("INJECT: %s (intensity=%d)", instance.name, intensity)

            # Execute injection
            inject_result = instance.run(components, stealth)

            # Validate
            if hasattr(instance, "validate"):
                probe_results = instance.validate(components)
                inject_result.probe_results = probe_results

            # Recommendations
            if hasattr(instance, "recommend"):
                inject_result.recommendations = instance.recommend()

            status_icon = (
                "✅"
                if inject_result.status == "passed"
                else "❌"
                if inject_result.status == "failed"
                else "⏭️"
            )
            self._logger.info(
                "%s Scenario %s: %s", status_icon, inject_result.scenario, inject_result.status
            )

            return inject_result

        except Exception as exc:
            self._logger.exception("Scenario %s raised exception: %s", scenario_cls.__name__, exc)
            return ScenarioResult(
                scenario=getattr(scenario_cls, "name", scenario_cls.__name__),
                status="error",
                reason=str(exc),
            )

    def _determine_verdict(self, result: ChaosRunResult) -> str:
        """Determine overall verdict based on results and regression."""
        if result.scenarios_failed > 0:
            return "fail"

        if result.regression and result.regression.get("failed", 0) > 0:
            return "fail"

        if result.scenarios_passed == 0 and result.scenarios_skipped > 0:
            return "skip"

        return "pass"
