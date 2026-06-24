"""Magenta CLI — Typer application and command groups."""


import typer

from magenta import __about__
from magenta.cli.automate import automate_app
from magenta.cli.chaos import chaos_app
from magenta.cli.dictator import dictator_app
from magenta.cli.health import health_app
from magenta.cli.lab import lab_app
from magenta.cli.orchestrate import orchestrate_app
from magenta.cli.response import response_app
from magenta.cli.state import state_app


def create_app() -> typer.Typer:
    app = typer.Typer(
        name="magenta",
        help="Agentic System Orchestration Automation and Response (ASOAR)",
        no_args_is_help=True,
        rich_markup_mode="rich",
        rich_help_panel=True,
    )

    app.add_typer(
        orchestrate_app,
        name="orchestrate",
        help="Manage missions, swarms, and orchestration lifecycle",
        rich_help_panel="Commands",
    )
    app.add_typer(
        automate_app,
        name="automate",
        help="Manage playbooks, rules, and automation triggers",
        rich_help_panel="Commands",
    )
    app.add_typer(
        response_app,
        name="response",
        help="Manage incidents, response actions, and approvals",
        rich_help_panel="Commands",
    )
    app.add_typer(
        health_app,
        name="health",
        help="System health checks for agents, models, pipeline, and storage",
        rich_help_panel="Commands",
    )
    app.add_typer(
        lab_app,
        name="lab",
        help="Simulation, testing, model comparison, and evaluation",
        rich_help_panel="Commands",
    )
    app.add_typer(
        dictator_app,
        name="dictator",
        help="Super-agent orchestration: command agents, probes, policies, and missions",
        rich_help_panel="Commands",
    )
    app.add_typer(
        state_app,
        name="state",
        help="Probe, attestation, and regression testing layer",
        rich_help_panel="Commands",
    )
    app.add_typer(
        chaos_app,
        name="chaos",
        help="Chaos engineering: fault injection, resilience validation, and certification",
        rich_help_panel="Commands",
    )

    @app.callback(invoke_without_command=True)
    def main(
        ctx: typer.Context,
        config: str | None = typer.Option(None, "--config", "-c", help="Path to config file"),
        env: str = typer.Option("dev", "--env", "-e", help="Environment (dev/staging/prod)"),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
        format: str = typer.Option("text", "--format", "-f", help="Output format (text/json)"),
        version: bool = typer.Option(False, "--version", help="Show version"),
    ):
        if version:
            typer.echo(f"Magenta v{__about__.__version__}")
            raise typer.Exit()

    return app
