"""Magenta dictator CLI — Super-agent orchestration commands."""

import json as json_mod

import typer

from magenta.agents.dictator import dictator
from magenta.cli.utils import (
    print_error,
    print_info,
    print_output,
    print_success,
    print_table,
    print_warning,
    status_badge,
)
from magenta.dictator.policies import OrchestrationPolicy

dictator_app = typer.Typer(
    name="dictator",
    help="Super-agent orchestration: command agents, probes, policies, and missions",
    no_args_is_help=True,
)


@dictator_app.command()
def status():
    """Show Dictator oversight board and framework status."""
    import asyncio

    board = asyncio.run(dictator.get_oversight_board())

    active_count = len(board.get("active_missions", {}))
    print_table(
        ["Metric", "Value"],
        [
            ["Dictator Status", status_badge(board.get("dictator_status", "unknown"))],
            ["Active Missions", str(active_count)],
            ["Completed Missions", str(board.get("completed_count", 0))],
            ["Total Directives", str(board.get("total_directives", 0))],
            ["Uptime (s)", f"{board.get('uptime', 0):.1f}"],
        ],
        title="Dictator Oversight Board",
    )

    for mid, oversight in board.get("active_missions", {}).items():
        print_table(
            ["Field", "Value"],
            [
                ["Mission ID", oversight["mission_id"][:12]],
                ["Teaming", oversight["teaming_structure"]],
                ["Agents", str(oversight["agent_count"])],
                ["Tasks", str(oversight["task_count"])],
                ["Probes", str(oversight["probe_count"])],
                ["Directives", str(oversight["directive_count"])],
            ],
            title=f"Mission: {mid[:12]}",
        )


@dictator_app.command()
def oversight(
    mission_id: str | None = typer.Option(None, "--mission", "-m", help="Mission ID"),
):
    """View Dictator oversight for all or a specific mission."""
    import asyncio

    if mission_id:
        result = asyncio.run(dictator.get_mission_oversight(mission_id))
        if not result:
            print_error(f"No oversight record for mission {mission_id[:12]}")
            raise typer.Exit(1)
        print_output(result, format="text")
    else:
        board = asyncio.run(dictator.get_oversight_board())
        missions = list(board.get("active_missions", {}).values())
        if not missions:
            print_info("No active missions")
            return
        print_table(
            ["Mission ID", "Teaming", "Agents", "Tasks", "Probes", "Directives"],
            [
                [
                    m["mission_id"][:12],
                    m["teaming_structure"],
                    str(m["agent_count"]),
                    str(m["task_count"]),
                    str(m["probe_count"]),
                    str(m["directive_count"]),
                ]
                for m in missions
            ],
            title="Active Mission Oversight",
        )


@dictator_app.command()
def directives(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of directives to show"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """View the Dictator directive log."""
    import asyncio

    log = asyncio.run(dictator.get_directive_log(limit=limit))
    if not log:
        print_info("No directives issued")
        return
    print_output(
        [
            {
                "type": d.get("type", ""),
                "target": d.get("target", ""),
                "mission": (d.get("mission_id") or "")[:12],
                "priority": d.get("priority", ""),
                "reason": d.get("reason", "")[:40],
                "timestamp": d.get("timestamp", "")[11:19],
            }
            for d in log
        ],
        format=format,
        columns=["Type", "Target", "Mission", "Priority", "Reason", "Time"],
    )


@dictator_app.command()
def halt(
    mission_id: str = typer.Argument(..., help="Mission ID to halt"),
    reason: str = typer.Option("Manual override", "--reason", "-r", help="Reason for halting"),
):
    """Immediately halt a running mission."""
    import asyncio

    try:
        result = asyncio.run(dictator.halt_mission(mission_id, reason))
        print_warning(f"Mission {mission_id[:12]} halted")
        print_output(result, format="text")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@dictator_app.command()
def escalate(
    mission_id: str = typer.Argument(..., help="Mission ID to escalate"),
    reason: str = typer.Option("", "--reason", "-r", help="Reason for escalation"),
):
    """Escalate a mission to human operators."""
    import asyncio

    try:
        result = asyncio.run(dictator.escalate_mission(mission_id, reason))
        print_warning(f"Mission {mission_id[:12]} escalated")
        print_output(result, format="text")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@dictator_app.command()
def deploy(
    role: str = typer.Argument(..., help="Agent role to deploy"),
    model: str | None = typer.Option(None, "--model", help="Model name"),
):
    """Deploy a new agent into the registry."""
    import asyncio

    try:
        kwargs = {}
        if model:
            kwargs["model_name"] = model
        agent = asyncio.run(dictator.deploy_agent(role, **kwargs))
        print_success(f"Deployed {role} agent: {agent.agent_id}")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@dictator_app.command()
def recall(
    agent_id: str = typer.Argument(..., help="Agent ID to recall"),
):
    """Recall (unregister) an agent."""
    import asyncio

    try:
        result = asyncio.run(dictator.recall_agent(agent_id))
        if result:
            print_success(f"Agent {agent_id} recalled")
        else:
            print_error(f"Agent {agent_id} not found")
            raise typer.Exit(1)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@dictator_app.command()
def override(
    mission_id: str = typer.Argument(..., help="Mission ID"),
    structure: str = typer.Argument(
        ..., help="Teaming structure: pipeline/supervisor/debate/mesh/referee"
    ),
):
    """Override teaming structure for a mission."""
    import asyncio

    try:
        result = asyncio.run(dictator.override_teaming(mission_id, structure))
        print_success(f"Teaming overridden to {structure} for {mission_id[:12]}")
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)


@dictator_app.command()
def policy(
    action: str = typer.Argument(..., help="Action: list/override/clear"),
    name: str | None = typer.Option(None, "--name", help="Policy name"),
    rules: str | None = typer.Option(None, "--rules", help="Policy rules as JSON"),
):
    """Manage orchestration policies."""
    import asyncio

    if action == "list":
        from magenta.dictator.policies import policy_engine

        policies = policy_engine._policies
        overrides = policy_engine._overrides

        print_table(
            ["Name", "Priority", "Enabled", "Rules"],
            [
                [p.name, str(p.priority), str(p.enabled), str(list(p.rules.keys()))[:40]]
                for p in policies
            ],
            title="Orchestration Policies",
        )

        if overrides:
            print_table(
                ["Override Name", "Rules"],
                [[n, str(p.rules)[:50]] for n, p in overrides.items()],
                title="Active Overrides",
            )

    elif action == "override":
        if not name or not rules:
            print_error("--name and --rules required for override")
            raise typer.Exit(1)
        policy = OrchestrationPolicy(name=name, rules=json_mod.loads(rules))
        result = asyncio.run(dictator.apply_policy_override(policy))
        print_success(f"Policy override applied: {name}")

    elif action == "clear":
        result = asyncio.run(dictator.clear_policy_overrides())
        print_success("All policy overrides cleared")

    else:
        print_error(f"Unknown action: {action}")
        raise typer.Exit(1)


@dictator_app.command()
def probe(
    action: str = typer.Argument(..., help="Action: promote"),
    name: str = typer.Option(..., "--name", "-n", help="Probe name"),
    guard: bool = typer.Option(False, "--guard", help="Promote to enforcement guard"),
):
    """Manage probes in the magnet layer."""
    import asyncio

    if action == "promote":
        result = asyncio.run(dictator.promote_probe(name, guard=guard))
        print_success(f"Probe '{name}' promoted" + (" to guard" if guard else ""))
    else:
        print_error(f"Unknown action: {action}")
        raise typer.Exit(1)


@dictator_app.command()
def framework():
    """Show comprehensive framework status from Dictator."""
    import asyncio

    fs = asyncio.run(dictator.get_framework_status())

    print_table(
        ["Domain", "Metric", "Value"],
        [
            ["Dictator", "Status", fs["dictator"]["status"]],
            ["Dictator", "Turns", str(fs["dictator"]["turn_count"])],
            ["Registry", "Total Agents", str(fs["registry"]["total_agents"])],
            ["Registry", "Roles", str(len(fs["registry"]["agents_by_role"]))],
            ["Missions", "Active", str(fs["missions"]["active"])],
            ["Missions", "Completed", str(fs["missions"]["completed"])],
            ["Missions", "Directives", str(fs["missions"]["directives"])],
            ["Policies", "Active", str(fs["policies"]["active"])],
            ["Policies", "Overrides", str(fs["policies"]["overrides"])],
            ["System", "Uptime (s)", f"{fs['uptime_seconds']:.1f}"],
        ],
        title="Magenta Framework Status",
    )
