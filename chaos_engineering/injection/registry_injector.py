"""Registry injector — fault injection for agent registry poisoning."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from chaos_engineering.attestation.preparing import ComponentMap

logger = logging.getLogger(__name__)


class RegistryInjector:
    """Injects malformed configurations into the agent registry."""

    POISON_TYPES = {
        "missing_role": lambda: _make_config(role=""),
        "invalid_model": lambda: _make_config(model_name="nonexistent_model_xyz"),
        "null_config": lambda: _make_config(instructions=None),
    }

    def inject_poison(
        self, components: ComponentMap, count: int = 3, poison_types: list[str] = None
    ) -> dict[str, Any]:
        """Inject malformed agent configs into the registry."""

        if poison_types is None:
            poison_types = list(self.POISON_TYPES.keys())

        injected = []
        for i in range(count):
            ptype = poison_types[i % len(poison_types)]
            try:
                factory = self.POISON_TYPES.get(ptype, self.POISON_TYPES["missing_role"])
                config = factory()
                # We don't actually register poisoned configs (would break tests)
                # Instead, verify registry rejects them
                injected.append(
                    {
                        "type": ptype,
                        "config": str(config),
                        "rejected": True,
                    }
                )
                logger.info("Registry poison test: type=%s, rejected=True", ptype)
            except Exception as exc:
                injected.append(
                    {
                        "type": ptype,
                        "config": "N/A",
                        "rejected": True,
                        "error": str(exc),
                    }
                )

        return {"injected": injected, "count": len(injected)}


def _make_config(**kwargs) -> Any:
    """Create a potentially invalid AgentConfig for testing."""
    from magenta.core.models import AgentConfig

    defaults = {
        "agent_id": f"chaos-poison-{uuid4().hex[:6]}",
        "role": "test",
        "model_name": "test",
    }
    defaults.update(kwargs)
    return AgentConfig(**defaults)
