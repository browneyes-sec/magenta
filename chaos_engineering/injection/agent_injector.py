"""Agent injector — fault injection primitives for agent registry manipulation."""

from __future__ import annotations

import logging
import random
from typing import Any

from chaos_engineering.attestation.preparing import ComponentMap

logger = logging.getLogger(__name__)


class AgentInjector:
    """Injects faults into the agent registry for chaos testing."""

    def remove_agents(self, components: ComponentMap, count: int = 1) -> dict[str, Any]:
        """Remove agents from the registry. Returns removed agent IDs."""
        from magenta.core.agent import agent_registry

        all_agents = agent_registry.all_agents()
        if not all_agents:
            return {"removed": [], "reason": "No agents in registry"}

        targets = random.sample(all_agents, min(count, len(all_agents)))
        removed = []

        for agent in targets:
            agent_id = agent.agent_id
            agent_registry.unregister(agent_id)
            removed.append(agent_id)
            logger.info("Removed agent: %s (role=%s)", agent_id, agent.role)

        return {
            "removed": removed,
            "count": len(removed),
            "remaining": len(agent_registry.all_agents()),
        }

    def corrupt_status(self, components: ComponentMap, count: int = 1) -> dict[str, Any]:
        """Set agent status to invalid values."""
        from magenta.core.agent import agent_registry

        all_agents = agent_registry.all_agents()
        if not all_agents:
            return {"corrupted": [], "reason": "No agents in registry"}

        targets = random.sample(all_agents, min(count, len(all_agents)))
        corrupted = []

        for agent in targets:
            original_status = str(agent.status)
            agent.status = "CHAOS_INVALID_STATUS"
            corrupted.append(
                {
                    "agent_id": agent.agent_id,
                    "original_status": original_status,
                }
            )
            logger.info("Corrupted agent status: %s", agent.agent_id)

        return {
            "corrupted": corrupted,
            "count": len(corrupted),
        }

    def restore_all(self, components: ComponentMap) -> dict[str, Any]:
        """Restore all agents to idle status."""
        from magenta.core.agent import agent_registry

        restored = 0
        for agent in agent_registry.all_agents():
            if str(agent.status) not in ("idle", "ready"):
                agent.status = "idle"
                restored += 1

        return {"restored": restored}
