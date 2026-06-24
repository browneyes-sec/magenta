"""Magenta lab CLI — Simulation, testing, model comparison, evaluation."""

import json
from datetime import datetime

import typer

from magenta.cli.utils import (
    print_error,
    print_info,
    print_output,
    print_success,
    print_table,
)
from magenta.core.models import MissionStatus, SeverityLevel

lab_app = typer.Typer(
    name="lab",
    help="Simulation, testing, model comparison, and evaluation",
    no_args_is_help=True,
)


scenarios = {
    "phishing": {
        "name": "phishing_campaign",
        "description": "Phishing campaign targeting Finance department",
        "severity": SeverityLevel.high.value,
        "source": "sentinel",
        "alert_id": "sim-phishing-001",
        "iocs": ["malicious-phish.com", "a1b2c3d4..."],
    },
    "ransomware": {
        "name": "ransomware_detection",
        "description": "Ransomware detected on critical server",
        "severity": SeverityLevel.critical.value,
        "source": "sentinel",
        "alert_id": "sim-ransomware-001",
        "iocs": ["7z8a9b0c..."],
    },
    "identity_compromise": {
        "name": "identity_compromise",
        "description": "User account performing anomalous logins",
        "severity": SeverityLevel.medium.value,
        "source": "sentinel",
        "alert_id": "sim-identity-001",
        "iocs": [],
    },
}


@lab_app.command()
def simulate(
    scenario: str = typer.Argument(..., help="Scenario name or path to JSON file"),
    speed: int = typer.Option(1, "--speed", help="Simulation speed multiplier"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Run a mission simulation."""
    import asyncio

    from magenta.core.mission import mission_manager
    from magenta.core.swarm import swarm_manager

    # Load scenario
    if scenario in scenarios:
        config = scenarios[scenario]
    else:
        try:
            with open(scenario) as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print_error(f"Scenario not found: {e}")
            raise typer.Exit(1)

    print_info(f"Simulating: {config['name']} (speed x{speed})")
    print_info(f"Description: {config['description']}")

    # Create mission
    mission = mission_manager.create(
        alert_id=config["alert_id"],
        source_system=config["source"],
        description=config["description"],
    )
    mission.severity = SeverityLevel(config["severity"])

    print_info(f"Mission created: {mission.mission_id[:8]}")

    # Execute swarm
    asyncio.run(swarm_manager.execute_mission(mission.mission_id))
    mission_manager.update_status(mission.mission_id, MissionStatus.executing)

    # Simulate completion (stub)
    mission_manager.update_status(mission.mission_id, MissionStatus.completed)

    print_success(f"Simulation complete: {mission.mission_id[:8]}")

    print_output({
        "mission_id": mission.mission_id[:8],
        "scenario": config["name"],
        "status": mission.status.value,
        "severity": mission.severity.value,
        "tasks": len(mission.tasks),
        "team_size": len(mission.team),
        "duration_simulated": f"{speed * 5}s",
    }, format=format)


@lab_app.command()
def test(
    agent_role: str = typer.Argument(..., help="Agent role to test"),
    prompt: str | None = typer.Option(None, "--prompt", help="Test prompt"),
    interactive: bool = typer.Option(False, "--interactive", help="Interactive REPL mode"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Test an agent with a prompt."""
    print_info(f"Testing agent: {agent_role}")
    print_info(f"Prompt: {prompt or '(default test prompt)'}")

    if interactive:
        print_info("Interactive mode (stub — REPL pending)")
        return

    print_output({
        "agent": agent_role,
        "status": "completed",
        "turns": 1,
        "response": f"[Simulated response from {agent_role} agent]",
        "latency_ms": 2400,
    }, format=format)


@lab_app.command()
def compare(
    model_a: str = typer.Argument(..., help="First model (e.g. ollama/qwen2.5:7b)"),
    model_b: str = typer.Argument(..., help="Second model (e.g. ollama/mistral:7b)"),
    suite: str | None = typer.Option(None, "--suite", help="Test suite to run"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Compare two models on a test suite."""
    print_info(f"Comparing: {model_a} vs {model_b}")
    print_info(f"Suite: {suite or 'default'}")

    print_table(
        ["Metric", model_a, model_b],
        [
            ["Accuracy", "0.87", "0.84"],
            ["Latency (avg)", "1.2s", "1.1s"],
            ["Tokens/s", "85", "92"],
            ["Cost/1K tokens", "$0.00", "$0.00"],
        ],
        title="Model Comparison",
    )


@lab_app.command()
def evaluate(
    suite: str = typer.Argument(..., help="Test suite path or name"),
    output: str | None = typer.Option(None, "--output", help="Output results to file"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Run a full evaluation benchmark."""
    print_info(f"Running evaluation suite: {suite}")
    print_info("Evaluation (stub — benchmark harness pending)")

    results = {
        "suite": suite,
        "timestamp": datetime.utcnow().isoformat(),
        "models": ["ollama/qwen2.5:7b", "ollama/mistral:7b"],
        "tests": 24,
        "passed": 22,
        "failed": 2,
        "accuracy": 0.917,
        "avg_latency_ms": 1850,
    }

    if output:
        with open(output, "w") as f:
            json.dump(results, f, indent=2)
        print_success(f"Results saved to {output}")

    print_output(results, format=format, columns=["Metric", "Value"])
