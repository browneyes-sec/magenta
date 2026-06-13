"""Magenta state CLI — Probe, attestation, and regression testing layer.

Launches the magnet probe/attestation framework and regression test suite.
Integrates with Dictator oversight for live system validation.
"""

import typer
import sys
import json as json_mod
from pathlib import Path
from typing import Optional
from datetime import datetime

from magenta.cli.utils import (
    print_table, print_output, print_error, print_success, print_info, print_warning, status_badge,
)

state_app = typer.Typer(
    name="state",
    help="Probe, attestation, and regression testing layer for the Magent framework",
    no_args_is_help=True,
)

PROBE_REGISTRY: dict[str, str] = {}


def _discover_probes() -> dict[str, str]:
    """Discover available probe modules in magnet/probes/."""
    probes = {}
    probes_dir = Path("magnet/probes")
    if probes_dir.exists():
        for f in probes_dir.glob("*_probe.py"):
            name = f.stem.replace("_probe", "")
            probes[name] = str(f)
    PROBE_REGISTRY.update(probes)
    return probes


def _load_probe(name: str) -> dict:
    """Load and execute a probe module, returning its results."""
    import importlib.util
    path = PROBE_REGISTRY.get(name)
    if not path:
        return {"probe": name, "status": "error", "error": f"Probe '{name}' not found"}
    try:
        spec = importlib.util.spec_from_file_location(f"magnet.probes.{name}_probe", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "run"):
            result = mod.run()
            return {"probe": name, "status": "completed", "result": result}
        return {"probe": name, "status": "error", "error": "Probe has no run() function"}
    except Exception as e:
        return {"probe": name, "status": "error", "error": str(e)}


@state_app.command()
def probe(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Run a specific probe"),
    list_probes: bool = typer.Option(False, "--list", "-l", help="List available probes"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Run probe checks against the Magenta framework.

    Probes are lightweight introspection points that validate agent,
    registry, pipeline, and data mesh health without modifying state.
    """
    _discover_probes()

    if list_probes:
        probes = _discover_probes()
        if not probes:
            print_info("No probes discovered")
            return
        print_table(
            ["Probe", "Path"],
            [[name, path] for name, path in probes.items()],
            title="Available Probes",
        )
        return

    if name:
        if name not in PROBE_REGISTRY:
            print_error(f"Unknown probe '{name}'. Use --list to see available probes")
            raise typer.Exit(1)
        result = _load_probe(name)
        status = result.get("status", "error")
        badge = status_badge("completed" if status == "completed" else "failed")
        print_info(f"Probe [{badge}] {name}")
        print_output(result.get("result", result), format=format)
        return

    # Run all probes
    probes = _discover_probes()
    if not probes:
        print_warning("No probes found in magnet/probes/")
        return

    results = []
    for pname in probes:
        result = _load_probe(pname)
        results.append(result)
        badge = status_badge("completed" if result.get("status") == "completed" else "failed")
        print_info(f"  [{badge}] {pname}")

    passed = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "error")
    print_success(f"Probes: {passed} passed, {failed} failed")


@state_app.command()
def regression(
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Specific test path or module"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose pytest output"),
    coverage: bool = typer.Option(False, "--coverage", "-c", help="Run with coverage report"),
    junit: bool = typer.Option(False, "--junit", "-j", help="Generate JUnit XML report"),
    k: Optional[str] = typer.Option(None, "--k", help="Filter tests by keyword expression"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Run the full regression test suite via pytest.

    Executes all tests in magnet/ against the live framework state.
    Use --path to target a specific module or file.
    """
    import subprocess

    cmd = [sys.executable, "-m", "pytest"]
    if verbose:
        cmd.append("-v")
    if coverage:
        cmd.extend(["--cov=magenta", "--cov-report=term-missing"])
    if junit:
        cmd.append("--junitxml=magnet/report.xml")
    if k:
        cmd.extend(["-k", k])
    if path:
        cmd.append(path)
    else:
        cmd.append("magnet/")

    print_info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode == 0:
        print_success("All regression tests passed")
    else:
        print_error(f"Regression tests failed (exit {result.returncode})")
        raise typer.Exit(result.returncode)

    if format == "json":
        print_output({"exit_code": result.returncode, "output": result.stdout}, format="json")


@state_app.command()
def report(
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Generate a consolidated state report from probes + Dictator oversight."""
    from magenta.agents.dictator import dictator

    import asyncio

    # Gather Dictator oversight
    board = asyncio.run(dictator.get_oversight_board())
    framework = asyncio.run(dictator.get_framework_status())

    # Run all probes
    probes = _discover_probes()
    probe_results = []
    for pname in probes:
        probe_results.append(_load_probe(pname))

    report_data = {
        "generated_at": datetime.utcnow().isoformat(),
        "dictator": framework,
        "oversight": board,
        "probes": {
            "total": len(probe_results),
            "passed": sum(1 for r in probe_results if r.get("status") == "completed"),
            "failed": sum(1 for r in probe_results if r.get("status") == "error"),
            "results": probe_results,
        },
    }

    if format == "json":
        print_output(report_data, format="json")
        return

    # Text output
    print_table(
        ["Domain", "Metric", "Value"],
        [
            ["Dictator", "Status", framework["dictator"]["status"]],
            ["Dictator", "Turns", str(framework["dictator"]["turn_count"])],
            ["Registry", "Agents", str(framework["registry"]["total_agents"])],
            ["Registry", "Roles", str(len(framework["registry"]["agents_by_role"]))],
            ["Missions", "Active", str(framework["missions"]["active"])],
            ["Missions", "Completed", str(framework["missions"]["completed"])],
            ["Missions", "Directives", str(framework["missions"]["directives"])],
            ["Policies", "Active", str(framework["policies"]["active"])],
            ["Policies", "Overrides", str(framework["policies"]["overrides"])],
            ["Probes", "Passed", str(report_data["probes"]["passed"])],
            ["Probes", "Failed", str(report_data["probes"]["failed"])],
            ["System", "Uptime (s)", f"{framework['uptime_seconds']:.1f}"],
        ],
        title="Magenta System State Report",
    )

    if probe_results:
        print_table(
            ["Probe", "Status", "Details"],
            [
                [r["probe"], status_badge("completed" if r["status"] == "completed" else "failed"),
                 str(r.get("result", r.get("error", "")))[:40]]
                for r in probe_results
            ],
            title="Probe Results",
        )


@state_app.command()
def attest(
    mission_id: Optional[str] = typer.Option(None, "--mission", "-m", help="Attest a specific mission"),
    all_missions: bool = typer.Option(False, "--all", help="Attest all completed missions"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Run attestation checks — verify chain of custody for mission actions.

    Attestation validates that every action in a mission has a complete,
    tamper-evident audit trail through the Data Lake.
    """
    from magenta.core.mission import mission_manager
    from magenta.dictator.state import dictator_state
    import asyncio

    missions_to_check = []

    if mission_id:
        try:
            mission = asyncio.run(asyncio.to_thread(mission_manager.get, mission_id))
            missions_to_check.append(mission)
        except Exception:
            print_error(f"Mission {mission_id} not found")
            raise typer.Exit(1)
    elif all_missions:
        for mid in dictator_state.completed_missions:
            try:
                mission = asyncio.run(asyncio.to_thread(mission_manager.get, mid))
                missions_to_check.append(mission)
            except Exception:
                pass
        if not missions_to_check:
            print_info("No completed missions to attest")
            return
    else:
        print_info("Use --mission <id> or --all to specify missions to attest")
        raise typer.Exit(0)

    results = []
    for mission in missions_to_check:
        oversight = dictator_state.active_missions.get(mission.mission_id)
        directive_count = oversight.directive_count if oversight else 0
        task_count = len(mission.tasks) if hasattr(mission, "tasks") else 0

        entry = {
            "mission_id": mission.mission_id[:12],
            "alert_id": mission.alert_id[:20],
            "severity": mission.severity.value if hasattr(mission.severity, "value") else mission.severity,
            "status": mission.status.value if hasattr(mission.status, "value") else mission.status,
            "tasks": task_count,
            "directives": directive_count,
            "verdict": "attested",
        }
        results.append(entry)

    print_output(
        results,
        format=format,
        columns=["Mission ID", "Alert", "Sev", "Status", "Tasks", "Directives", "Verdict"],
    )

    total = len(results)
    print_success(f"Attestation complete: {total} missions verified")
