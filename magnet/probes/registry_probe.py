"""Registry probe — validates agent registry health and availability."""

from magenta.core.agent import agent_registry


def run() -> dict:
    """Check agent registry health."""
    all_agents = agent_registry.all_agents()
    by_role = agent_registry.counts

    available = sum(1 for a in all_agents if hasattr(a, "status") and str(a.status) in ("idle", "ready"))

    return {
        "total_agents": len(all_agents),
        "roles": len(by_role),
        "available": available,
        "roles_detail": by_role,
    }
