"""Magenta automate CLI — Playbook, rule, and trigger management."""

import typer
from typing import Optional, List

from magenta.core.playbook import playbook_manager
from magenta.cli.utils import (
    print_table, print_output, print_error, print_success, print_info, status_badge
)

automate_app = typer.Typer(
    name="automate",
    help="Manage playbooks, rules, and automation triggers",
    no_args_is_help=True,
)

# --- Playbook sub-group ---
playbook_app = typer.Typer(name="playbook", help="Manage playbooks")
automate_app.add_typer(playbook_app)


@playbook_app.command("list")
def playbook_list(
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """List registered playbooks."""
    playbooks = playbook_manager.list(tag=tag)
    if not playbooks:
        print_info("No playbooks registered")
        return

    print_output(
        [
            {
                "name": p.name,
                "version": p.version,
                "tags": ", ".join(p.tags),
                "stages": len(p.stages),
                "updated": p.updated_at.isoformat()[:10],
            }
            for p in playbooks
        ],
        format=format,
        columns=["Name", "Version", "Tags", "Stages", "Updated"],
    )


@playbook_app.command("apply")
def playbook_apply(
    path: str = typer.Argument(..., help="Playbook file path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without registering"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Register or update a playbook."""
    try:
        pb = playbook_manager.load(path)
        errors = playbook_manager.validate(path)
        if errors:
            for e in errors:
                print_error(f"Validation: {e}")
            raise typer.Exit(1)

        if dry_run:
            from magenta.cli.utils import print_json
            print_info("[DRY RUN] Would register playbook:")
            print_json(pb.model_dump())
            return

        playbook_manager.register(pb)
        print_success(f"Playbook '{pb.name}' v{pb.version} registered")
        print_output({
            "name": pb.name,
            "version": pb.version,
            "stages": len(pb.stages),
        }, format=format)

    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@playbook_app.command("validate")
def playbook_validate(
    path: str = typer.Argument(..., help="Playbook file path"),
):
    """Validate playbook schema without registering."""
    errors = playbook_manager.validate(path)
    if errors:
        for e in errors:
            print_error(e)
        raise typer.Exit(1)
    print_success(f"Playbook '{path}' is valid")


@playbook_app.command("show")
def playbook_show(
    name: str = typer.Argument(..., help="Playbook name"),
    version: Optional[str] = typer.Option(None, "--version", help="Version"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Show playbook details."""
    pb = playbook_manager.get(name, version=version)
    if not pb:
        print_error(f"Playbook '{name}' not found")
        raise typer.Exit(1)

    print_output(pb.model_dump(), format=format,
                 columns=["Field", "Value"])


# --- Rule sub-group ---
rule_app = typer.Typer(name="rule", help="Manage routing rules")
automate_app.add_typer(rule_app)


@rule_app.command("list")
def rule_list(
    enabled_only: bool = typer.Option(False, "--enabled-only", help="Show only enabled rules"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """List routing rules."""
    # Stub — rules stored in data layer
    print_info("Rules (stub — data layer integration pending)")
    print_output([
        {"id": "rule-001", "name": "phishing-auto-contain", "enabled": True},
        {"id": "rule-002", "name": "ransomware-escalate", "enabled": True},
    ], format=format, columns=["ID", "Name", "Enabled"])


@rule_app.command("add")
def rule_add(
    path: str = typer.Argument(..., help="Rule file path (YAML)"),
):
    """Add a routing rule."""
    print_success(f"Rule from '{path}' added (stub)")


@rule_app.command("toggle")
def rule_toggle(
    rule_id: str = typer.Argument(..., help="Rule ID"),
):
    """Enable/disable a rule."""
    print_success(f"Rule {rule_id} toggled (stub)")


# --- Trigger sub-group ---
trigger_app = typer.Typer(name="trigger", help="Manage triggers")
automate_app.add_typer(trigger_app)


@trigger_app.command("list")
def trigger_list(
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """List configured triggers."""
    print_info("Triggers (stub — integration pending)")
    print_output([
        {"name": "sentinel-incident-webhook", "type": "webhook", "enabled": True},
        {"name": "splunk-alert-poll", "type": "poll", "enabled": True},
    ], format=format, columns=["Name", "Type", "Enabled"])


@trigger_app.command("enable")
def trigger_enable(
    name: str = typer.Argument(..., help="Trigger name"),
):
    """Enable a trigger."""
    print_success(f"Trigger '{name}' enabled (stub)")


@trigger_app.command("disable")
def trigger_disable(
    name: str = typer.Argument(..., help="Trigger name"),
):
    """Disable a trigger."""
    print_info(f"Trigger '{name}' disabled (stub)")
