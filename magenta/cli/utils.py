"""CLI utilities: table rendering, JSON output, formatting."""

import json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


def print_table(columns: list[str], rows: list[list[Any]], title: str = "") -> None:
    """Print a rich formatted table."""
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(cell) for cell in row])
    console.print(table)


def print_json(data: Any) -> None:
    """Print data as formatted JSON."""
    console.print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def print_output(data: Any, format: str = "text", columns: list[str] | None = None) -> None:
    """Print output in requested format."""
    if format == "json":
        print_json(data)
    elif format == "text" and isinstance(data, list) and columns:
        rows = []
        for item in data:
            if isinstance(item, dict):
                rows.append([str(item.get(c, "")) for c in columns])
            else:
                rows.append([str(item)])
        print_table(columns, rows)
    else:
        console.print(data)


def print_error(msg: str) -> None:
    """Print an error message."""
    console.print(f"[red]ERROR:[/red] {msg}")


def print_success(msg: str) -> None:
    """Print a success message."""
    console.print(f"[green]OK:[/green] {msg}")


def print_info(msg: str) -> None:
    """Print an info message."""
    console.print(f"[blue]{msg}[/blue]")


def print_warning(msg: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]WARNING:[/yellow] {msg}")


def status_badge(status: str) -> str:
    """Return colored status badge."""
    colors = {
        "healthy": "green",
        "degraded": "yellow",
        "down": "red",
        "active": "green",
        "completed": "blue",
        "failed": "red",
        "pending": "yellow",
        "approved": "green",
        "rejected": "red",
    }
    color = colors.get(status.lower(), "white")
    return f"[{color}]{status}[/{color}]"
