"""Dictator probe — validates Dictator oversight and directive health."""

import asyncio

from magenta.agents.dictator import dictator


def run() -> dict:
    """Check Dictator oversight health."""
    board = asyncio.run(dictator.get_oversight_board())

    return {
        "status": board.get("dictator_status", "unknown"),
        "active_missions": len(board.get("active_missions", {})),
        "completed_missions": board.get("completed_count", 0),
        "total_directives": board.get("total_directives", 0),
        "uptime_seconds": round(board.get("uptime", 0), 1),
        "healthy": board.get("dictator_status") in ("idle", "commanding", "reviewing"),
    }
