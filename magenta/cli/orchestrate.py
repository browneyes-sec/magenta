"""Magenta orchestrate CLI — Mission lifecycle management."""

from datetime import datetime

import typer

from magenta.cli.utils import (
    print_error,
    print_info,
    print_output,
    print_success,
    print_table,
    status_badge,
)
from magenta.core.mission import mission_manager
from magenta.core.playbook import playbook_manager
from magenta.core.swarm import swarm_manager

orchestrate_app = typer.Typer(
    name="orchestrate",
    help="Manage missions, swarms, and orchestration lifecycle",
    no_args_is_help=True,
)


@orchestrate_app.command()
def start(
    playbook: str = typer.Argument(..., help="Playbook file path or incident ID"),
    params: str | None = typer.Option(None, "--params", help="JSON mission parameters"),
    from_incident: bool = typer.Option(
        False, "--from-incident", help="Treat argument as incident ID"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without executing"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Start a new mission from a playbook or incident ID."""
    import json as json_mod

    try:
        if from_incident:
            mission = mission_manager.create(
                alert_id=playbook,
                source_system="sentinel",
                description=f"Mission from incident {playbook}",
            )
        else:
            pb = playbook_manager.load(playbook)
            playbook_manager.register(pb)
            mission = mission_manager.create(
                alert_id=playbook,
                source_system="sentinel",
                playbook=pb,
                description=pb.description,
            )

        if params:
            extra = json_mod.loads(params)
            mission.artifact_bundle.update(extra)

        if dry_run:
            print_info(f"[DRY RUN] Would start mission: {mission.mission_id}")
            print_json(mission.model_dump())
            return

        import asyncio

        asyncio.run(swarm_manager.execute_mission(mission.mission_id))

        print_success(f"Mission started: {mission.mission_id}")
        print_output(
            {
                "mission_id": mission.mission_id,
                "status": mission.status.value,
                "tasks": len(mission.tasks),
                "agents": len(mission.team),
                "created_at": mission.created_at.isoformat(),
            },
            format=format,
        )

    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@orchestrate_app.command()
def stop(
    mission_id: str = typer.Argument(..., help="Mission ID to stop"),
    force: bool = typer.Option(False, "--force", help="Force stop without graceful shutdown"),
):
    """Stop a running mission."""
    try:
        import asyncio

        asyncio.run(swarm_manager.cancel_mission(mission_id))
        print_success(f"Mission {mission_id} stopped")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@orchestrate_app.command()
def status(
    mission_id: str = typer.Argument(..., help="Mission ID"),
    watch: bool = typer.Option(False, "--watch", help="Continuously watch status"),
):
    """Show mission status and agent assignments."""
    try:
        mission = mission_manager.get(mission_id)
        agents = swarm_manager.get_mission_agents(mission_id)

        print_table(
            ["Field", "Value"],
            [
                ["Mission ID", mission.mission_id],
                ["Status", status_badge(mission.status.value)],
                ["Alert ID", mission.alert_id],
                ["Severity", str(mission.severity.value)],
                ["Risk Score", str(mission.risk_score)],
                ["Tasks", str(len(mission.tasks))],
                ["Team Size", str(len(mission.team))],
                ["Created", mission.created_at.isoformat()],
                ["Updated", mission.updated_at.isoformat()],
            ],
            title=f"Mission: {mission_id[:8]}",
        )

        if agents:
            print_table(
                ["Task ID", "Type", "Role", "Agent", "Status"],
                [
                    [
                        a["task_id"][:16],
                        a["task_type"],
                        a["role"],
                        a["agent_id"][:16] if a["agent_id"] else "unassigned",
                        status_badge(a["status"]),
                    ]
                    for a in agents
                ],
                title="Agent Assignments",
            )

    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@orchestrate_app.command()
def list_(
    status_filter: str | None = typer.Option(
        None, "--status", help="Filter: active/completed/failed/all"
    ),
    limit: int = typer.Option(50, "--limit", help="Max results"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """List all missions."""
    missions = mission_manager.list(status=status_filter)[:limit]

    if not missions:
        print_info("No missions found")
        return

    print_output(
        [
            {
                "mission_id": m.mission_id[:8],
                "status": m.status.value,
                "alert_id": m.alert_id[:30],
                "severity": m.severity.value,
                "tasks": len(m.tasks),
                "created": m.created_at.isoformat()[:19],
            }
            for m in missions
        ],
        format=format,
        columns=["Mission ID", "Status", "Alert", "Sev", "Tasks", "Created"],
    )


@orchestrate_app.command()
def logs(
    mission_id: str = typer.Argument(..., help="Mission ID"),
    tail: int | None = typer.Option(None, "--tail", help="Show last N lines"),
    level: str | None = typer.Option(None, "--level", help="Filter: DEBUG/INFO/WARN/ERROR"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """View mission execution logs."""
    mission = mission_manager.get(mission_id)
    print_info(f"Logs for mission {mission_id[:8]} (stub — registry integration pending)")
    print_output(
        [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "message": "Mission created",
            },
            {
                "timestamp": mission.created_at.isoformat(),
                "level": "INFO",
                "message": f"Status: {mission.status.value}",
            },
        ],
        format=format,
        columns=["Timestamp", "Level", "Message"],
    )


# Alias for list since 'list' is a reserved word
orchestrate_app.command(name="list")(list_)
