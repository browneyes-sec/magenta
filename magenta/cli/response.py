"""Magenta response CLI — Incident, action, and approval management."""

from datetime import datetime

import typer

from magenta.cli.utils import (
    print_error,
    print_info,
    print_output,
    print_success,
)

response_app = typer.Typer(
    name="response",
    help="Manage incidents, response actions, and approvals",
    no_args_is_help=True,
)

# --- Actions sub-group ---
actions_app = typer.Typer(name="actions", help="Manage response actions")
response_app.add_typer(actions_app)


@actions_app.command("list")
def actions_list(
    role: str | None = typer.Option(None, "--role", help="Filter by agent role"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """List available response actions."""
    actions = [
        {"name": "disable_account", "role": "contain", "risk": 60, "approval": True},
        {"name": "isolate_host", "role": "contain", "risk": 80, "approval": True},
        {"name": "block_ip", "role": "contain", "risk": 50, "approval": True},
        {"name": "block_url", "role": "contain", "risk": 30, "approval": False},
        {"name": "reset_password", "role": "identity", "risk": 40, "approval": True},
        {"name": "enable_mfa", "role": "identity", "risk": 20, "approval": False},
        {"name": "create_ticket", "role": "report", "risk": 5, "approval": False},
        {"name": "notify_user", "role": "report", "risk": 5, "approval": False},
    ]

    if role:
        actions = [a for a in actions if a["role"] == role]

    print_output(
        actions,
        format=format,
        columns=["Name", "Role", "Risk", "Approval"],
    )


@actions_app.command("describe")
def actions_describe(
    action_name: str = typer.Argument(..., help="Action name"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Show action details, parameters, and risk."""
    actions_db = {
        "disable_account": {
            "name": "disable_account",
            "description": "Disable a user account in Entra ID",
            "risk": 60,
            "requires_approval": True,
            "parameters": [
                {"name": "user_principal_name", "type": "string", "required": True},
                {"name": "reason", "type": "enum", "values": ["compromised", "malicious", "policy"]},
            ],
            "auth": "managed_identity",
        },
        "isolate_host": {
            "name": "isolate_host",
            "description": "Isolate a device from network in Defender ATP",
            "risk": 80,
            "requires_approval": True,
            "parameters": [
                {"name": "device_id", "type": "string", "required": True},
                {"name": "isolation_type", "type": "enum", "values": ["full", "selective"]},
            ],
        },
    }

    action = actions_db.get(action_name)
    if not action:
        print_error(f"Unknown action: {action_name}")
        raise typer.Exit(1)

    print_output(action, format=format, columns=["Field", "Value"])


@actions_app.command("execute")
def actions_execute(
    action_name: str = typer.Argument(..., help="Action to execute"),
    target: str = typer.Option("", "--target", help="Target entity identifier"),
    reason: str = typer.Option("", "--reason", help="Reason code"),
    force: bool = typer.Option(False, "--force", help="Skip approval gate"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Execute a response action."""
    print_info(f"Executing '{action_name}' on target '{target or 'N/A'}'")
    if not force:
        print_info("Risk assessment required (stub — approval gate pending)")
    print_success(f"Action '{action_name}' executed (stub)")

    print_output({
        "action": action_name,
        "target": target,
        "status": "queued",
        "requires_approval": not force,
        "execution_id": f"exec-{datetime.utcnow().timestamp():.0f}",
    }, format=format)


# --- Approval sub-group ---
approval_app = typer.Typer(name="approval", help="Manage approvals")
response_app.add_typer(approval_app)


@approval_app.command("list")
def approval_list(
    queue: bool = typer.Option(False, "--queue", help="Show queue depth"),
    role: str | None = typer.Option(None, "--role", help="Filter by agent role"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """List pending approvals."""
    print_info("Pending approvals (stub — data layer integration pending)")
    print_output([
        {"id": "apr-001", "action": "disable_account", "target": "user@fin.com",
         "risk": 65, "agent": "contain_agent", "status": "pending"},
        {"id": "apr-002", "action": "isolate_host", "target": "FIN-PROD-347",
         "risk": 80, "agent": "contain_agent", "status": "pending"},
    ], format=format, columns=["ID", "Action", "Target", "Risk", "Agent", "Status"])


@approval_app.command("approve")
def approval_approve(
    approval_id: str = typer.Argument(..., help="Approval ID"),
    comment: str = typer.Option("", "--comment", help="Approval comment"),
):
    """Approve a pending action."""
    print_success(f"Approval {approval_id} approved{f' — {comment}' if comment else ''}")


@approval_app.command("reject")
def approval_reject(
    approval_id: str = typer.Argument(..., help="Approval ID"),
    reason: str = typer.Option("", "--reason", help="Rejection reason"),
):
    """Reject a pending action."""
    print_info(f"Approval {approval_id} rejected{f' — {reason}' if reason else ''}")


# --- Incidents sub-group ---
incidents_app = typer.Typer(name="incidents", help="Manage incidents")
response_app.add_typer(incidents_app)


@incidents_app.command("list")
def incidents_list(
    severity: str | None = typer.Option(None, "--severity", help="Filter by severity"),
    status: str | None = typer.Option(None, "--status", help="Filter by status"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """List active incidents."""
    print_info("Incidents (stub — Sentinel integration pending)")
    print_output([
        {"id": "inc-8932", "severity": "high", "status": "active",
         "source": "Sentinel", "created": "2026-06-13T18:00:00Z"},
        {"id": "inc-8933", "severity": "medium", "status": "active",
         "source": "Splunk", "created": "2026-06-13T18:30:00Z"},
    ], format=format, columns=["ID", "Severity", "Status", "Source", "Created"])


@incidents_app.command("show")
def incidents_show(
    incident_id: str = typer.Argument(..., help="Incident ID"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Show incident details."""
    print_info(f"Incident {incident_id} details (stub — integration pending)")
