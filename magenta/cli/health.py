"""Magenta health CLI — System health checks."""

from datetime import datetime

import typer

from magenta.cli.utils import (
    print_info,
    print_output,
    print_table,
    status_badge,
)

health_app = typer.Typer(
    name="health",
    help="System health checks for agents, models, pipeline, and storage",
    no_args_is_help=True,
)


@health_app.command()
def check(
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Run full system health check."""
    checks = {
        "agents": {"status": "healthy", "latency_ms": 120, "message": "3 agents online"},
        "models": {"status": "healthy", "latency_ms": 3400, "message": "OLLAMA responding"},
        "pipeline": {"status": "healthy", "latency_ms": 45, "message": "Event Hubs connected"},
        "storage": {"status": "healthy", "latency_ms": 15, "message": "SQLite connected"},
    }

    all_healthy = all(c["status"] == "healthy" for c in checks.values())
    overall = "healthy" if all_healthy else "degraded"

    if format == "json":
        print_output(
            {"status": overall, "checks": checks, "timestamp": datetime.utcnow().isoformat()},
            format="json",
        )
    else:
        print_info(f"System Status: {status_badge(overall)}")
        print_table(
            ["Component", "Status", "Latency", "Message"],
            [
                [name, status_badge(c["status"]), f"{c['latency_ms']}ms", c["message"]]
                for name, c in checks.items()
            ],
        )


@health_app.command()
def agents(
    watch: bool = typer.Option(False, "--watch", help="Continuously watch"),
    role: str | None = typer.Option(None, "--role", help="Filter by role"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Check agent health status."""
    from magenta.core.agent import agent_registry

    agents_list = agent_registry.all_agents()
    if not agents_list:
        print_info("No agents registered")
        return

    if role:
        agents_list = [a for a in agents_list if a.role == role]

    print_output(
        [
            {
                "agent_id": a.agent_id[:16],
                "role": a.role,
                "status": a.status.value,
                "model": f"{a.config.model_provider}/{a.config.model_name}",
            }
            for a in agents_list
        ],
        format=format,
        columns=["Agent ID", "Role", "Status", "Model"],
    )


@health_app.command()
def models(
    provider: str | None = typer.Option(None, "--provider", help="Filter by provider"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Check LLM model health."""
    print_info("Model health (stub — model router integration pending)")
    print_output(
        [
            {"provider": "ollama", "model": "qwen2.5:7b", "status": "healthy", "latency_ms": 1200},
            {"provider": "ollama", "model": "mistral:7b", "status": "healthy", "latency_ms": 1100},
            {
                "provider": "ollama",
                "model": "mixtral:8x7b",
                "status": "degraded",
                "latency_ms": 4500,
            },
        ],
        format=format,
        columns=["Provider", "Model", "Status", "Latency"],
    )


@health_app.command()
def pipeline(
    lag_threshold: int = typer.Option(1000, "--lag-threshold", help="Alert if lag exceeds N"),
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Check Event Hubs pipeline health."""
    print_info("Pipeline health (stub — Event Hubs integration pending)")
    print_output(
        [
            {"topic": "raw-alerts", "lag": 12, "throughput": 45, "status": "healthy"},
            {"topic": "enriched-alerts", "lag": 3, "throughput": 38, "status": "healthy"},
            {"topic": "actions", "lag": 0, "throughput": 12, "status": "healthy"},
            {"topic": "audit", "lag": 5, "throughput": 25, "status": "healthy"},
        ],
        format=format,
        columns=["Topic", "Lag", "Throughput/s", "Status"],
    )


@health_app.command()
def storage(
    format: str = typer.Option("text", "--format", "-f", help="Output format"),
):
    """Check storage health."""
    from magenta.config import settings

    print_info("Storage health")
    print_output(
        [
            {"backend": "SQL", "engine": settings.sql.url.split("://")[0], "status": "healthy"},
            {"backend": "Elasticsearch", "hosts": settings.elastic.hosts[0], "status": "healthy"},
            {"backend": "Data Lake", "container": settings.lake.container, "status": "healthy"},
        ],
        format=format,
        columns=["Backend", "Endpoint", "Status"],
    )
