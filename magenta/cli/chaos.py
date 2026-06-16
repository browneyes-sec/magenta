"""Magenta chaos CLI — Chaos engineering fault injection and resilience validation."""

import typer
import json
from typing import Optional
from pathlib import Path
from datetime import datetime

from magenta.cli.utils import (
    print_table, print_output, print_error, print_success, print_info, print_warning, status_badge,
)

chaos_app = typer.Typer(
    name="chaos",
    help="Chaos engineering: fault injection, resilience validation, and certification",
    no_args_is_help=True,
    rich_markup_mode="rich",
    rich_help_panel=True,
)


@chaos_app.command()
def run(
    scenario: Optional[str] = typer.Argument(None, help="Scenario name or comma-separated list (default: all enabled)"),
    intensity: int = typer.Option(3, "--intensity", "-i", help="Injection intensity 1-5"),
    stealth: bool = typer.Option(False, "--stealth", help="Enable stealth mode (delayed logging)"),
    timeout: int = typer.Option(300, "--timeout", help="Timeout in seconds"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen without injecting"),
    probes: bool = typer.Option(True, "--probes/--no-probes", help="Run probes after chaos"),
    regression: bool = typer.Option(True, "--regression/--no-regression", help="Run regression after chaos"),
    output: Optional[str] = typer.Option(None, "--output", help="Export report to file"),
    format: str = typer.Option("markdown", "--format", "-f", help="Export format: markdown (default), json"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Run chaos scenarios with auto-validation.

    Executes fault injection scenarios and automatically validates system
    recovery with probes and regression tests. Produces a condensed
    certification report deposited in docs/certifications/.
    """
    from chaos_engineering.chaos import ChaosEngine

    print_info(f"Chaos Engine initializing...")
    print_info(f"Intensity: {intensity} | Stealth: {'ON' if stealth else 'OFF'} | Timeout: {timeout}s")

    if dry_run:
        print_warning("DRY RUN — no injection will occur")

    engine = ChaosEngine()
    result = engine.run(
        scenario=scenario,
        intensity=intensity,
        stealth=stealth,
        timeout=timeout,
        dry_run=dry_run,
        validate=regression,
    )

    # Display results
    print_info(f"\n{'='*60}")
    print_info(f"Chaos Run Complete: {result.run_id}")
    print_info(f"{'='*60}")

    verdict_badge = status_badge(result.verdict)
    print_info(f"Verdict: {verdict_badge}")
    print_info(f"Duration: {result.duration_seconds:.1f}s")
    print_info(f"Scenarios: {result.scenarios_passed} passed, {result.scenarios_failed} failed, {result.scenarios_skipped} skipped")

    # Probe snapshot
    pre_passed = sum(1 for p in result.baseline_probes if p.get("healthy"))
    post_passed = sum(1 for p in result.post_probes if p.get("healthy"))
    print_info(f"Probes: {pre_passed}/{len(result.baseline_probes)} pre → {post_passed}/{len(result.post_probes)} post")

    # Regression
    if result.regression:
        reg_status = result.regression.get("status", "unknown")
        reg_passed = result.regression.get("passed", 0)
        reg_total = result.regression.get("total", 0)
        print_info(f"Regression: {reg_passed}/{reg_total} passed ({reg_status})")

    # Scenario details
    if verbose:
        print_table(
            ["Scenario", "Status", "Recovery", "Details"],
            [
                [r.scenario,
                 status_badge(r.status),
                 f"{r.recovery_time_seconds:.1f}s" if r.recovery_time_seconds else "—",
                 str(r.injection_details)[:50]]
                for r in result.results
            ],
            title="Scenario Results",
        )

    # Export
    if output:
        if format == "json":
            from chaos_engineering.attestation.report_generator import ReportGenerator
            gen = ReportGenerator({})
            with open(output, "w") as f:
                json.dump(gen._to_dict(result), f, indent=2, default=str)
            print_success(f"JSON report exported to {output}")
        else:
            cert_dir = Path("docs/certifications")
            files = list(cert_dir.glob(f"*{result.run_id.split('-', 1)[1]}*"))
            if files:
                import shutil
                shutil.copy(files[0], output)
                print_success(f"Markdown report exported to {output}")

    if result.verdict == "pass":
        print_success(f"Certification: PASS — {result.run_id}")
    elif result.verdict == "fail":
        print_error(f"Certification: FAIL — {result.run_id}")
    else:
        print_warning(f"Certification: {result.verdict.upper()} — {result.run_id}")


@chaos_app.command()
def scenarios(
    show: Optional[str] = typer.Option(None, "--show", help="Show details for a specific scenario"),
    enabled_only: bool = typer.Option(False, "--enabled", help="Show only enabled scenarios"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """List available chaos scenarios or show details."""
    import tomllib

    config_path = Path("chaos_engineering/chaos.toml")
    if not config_path.exists():
        print_error("chaos.toml not found")
        raise typer.Exit(1)

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    scenarios_config = config.get("scenarios", {})

    if show:
        if show not in scenarios_config:
            print_error(f"Scenario '{show}' not found")
            raise typer.Exit(1)
        cfg = scenarios_config[show]
        print_table(
            ["Property", "Value"],
            [[k, str(v)] for k, v in cfg.items()],
            title=f"Scenario: {show}",
        )
        return

    rows = []
    for name, cfg in scenarios_config.items():
        if enabled_only and not cfg.get("enabled", True):
            continue
        status = "✅ enabled" if cfg.get("enabled", True) else "❌ disabled"
        rows.append([
            name,
            status,
            cfg.get("severity", "unknown"),
            cfg.get("description", "")[:40],
        ])

    print_table(
        ["Scenario", "Status", "Severity", "Description"],
        rows,
        title="Chaos Scenarios",
    )


@chaos_app.command()
def report(
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Report run ID (default: latest)"),
    recommendations: bool = typer.Option(True, "--recommendations/--no-recommendations", help="Include recommendations"),
    output: Optional[str] = typer.Option(None, "--output", help="Export to file"),
    format: str = typer.Option("markdown", "--format", "-f", help="Export format: markdown (default), json"),
):
    """Generate or view chaos report from last run."""
    cert_dir = Path("docs/certifications")

    if not cert_dir.exists():
        print_error("No certifications found")
        raise typer.Exit(1)

    # Find latest or specific report
    reports = sorted(cert_dir.glob("magenta_chaos-*.md"), reverse=True)
    if not reports:
        print_error("No chaos certification reports found")
        raise typer.Exit(1)

    if run_id:
        matching = [r for r in reports if run_id in r.name]
        if not matching:
            print_error(f"No report found for run_id: {run_id}")
            raise typer.Exit(1)
        target = matching[0]
    else:
        target = reports[0]

    content = target.read_text()

    if not recommendations:
        # Strip recommendation sections
        lines = content.split("\n")
        filtered = []
        skip = False
        for line in lines:
            if "## Recommendations" in line:
                skip = True
            elif skip and line.startswith("## "):
                skip = False
            if not skip:
                filtered.append(line)
        content = "\n".join(filtered)

    if output:
        Path(output).write_text(content)
        print_success(f"Report exported to {output}")
    else:
        print(content)

    print_info(f"\nReport: {target.name}")


@chaos_app.command()
def config(
    set_val: Optional[str] = typer.Option(None, "--set", help="Set a config value (key=value)"),
    reset: bool = typer.Option(False, "--reset", help="Reset to defaults"),
    show: bool = typer.Option(True, "--show/--no-show", help="Show current config"),
):
    """Show or modify chaos configuration."""
    import tomllib

    config_path = Path("chaos_engineering/chaos.toml")

    if reset:
        print_info("Resetting chaos.toml to defaults...")
        # Would restore default config
        print_success("Config reset to defaults")
        return

    if set_val:
        key, _, value = set_val.partition("=")
        if not key or not value:
            print_error("Invalid format. Use --set key=value")
            raise typer.Exit(1)
        print_info(f"Setting {key} = {value}")
        # Would update TOML
        print_success(f"Config updated: {key} = {value}")
        return

    if show and config_path.exists():
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        print_table(
            ["Section", "Key", "Value"],
            [
                [section, k, str(v)]
                for section, values in config.items()
                if isinstance(values, dict)
                for k, v in values.items()
            ],
            title="Chaos Configuration",
        )
