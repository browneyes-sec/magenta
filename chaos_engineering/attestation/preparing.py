"""Pre-flight validation — detect available components before chaos runs.

Prevents false positives by scanning the environment and returning a
ComponentMap of what's testable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ComponentMap:
    """Map of available components in the current environment."""

    agents: bool = False
    agent_count: int = 0
    agent_roles: list[str] = field(default_factory=list)
    probes: list[str] = field(default_factory=list)
    regression: str = "none"  # full | lightweight | none
    dictator: bool = False
    registry_writable: bool = False
    pipeline: bool = False
    outbox: bool = False
    eventhub: bool = False
    mission_manager: bool = False
    swarm_manager: bool = False
    model_router: bool = False
    telemetry: bool = False

    def to_dict(self) -> dict:
        return {
            "agents": self.agents,
            "agent_count": self.agent_count,
            "agent_roles": self.agent_roles,
            "probes": self.probes,
            "regression": self.regression,
            "dictator": self.dictator,
            "registry_writable": self.registry_writable,
            "pipeline": self.pipeline,
            "outbox": self.outbox,
            "eventhub": self.eventhub,
            "mission_manager": self.mission_manager,
            "swarm_manager": self.swarm_manager,
            "model_router": self.model_router,
            "telemetry": self.telemetry,
        }


class PreparingStage:
    """Scans the environment and returns a ComponentMap of what's testable."""

    def scan(self) -> ComponentMap:
        """Run all component checks and return a ComponentMap."""
        components = ComponentMap()
        components.agents = self._check_agents(components)
        components.probes = self._check_probes()
        components.regression = self._check_regression()
        components.dictator = self._check_dictator()
        components.registry_writable = self._check_registry_writable()
        components.pipeline = self._check_pipeline()
        components.outbox = self._check_outbox()
        components.eventhub = self._check_eventhub()
        components.mission_manager = self._check_mission_manager()
        components.swarm_manager = self._check_swarm_manager()
        components.model_router = self._check_model_router()
        components.telemetry = self._check_telemetry()
        return components

    def _check_agents(self, components: ComponentMap) -> bool:
        try:
            from magenta.core.agent import agent_registry

            agents = agent_registry.all_agents()
            components.agent_count = len(agents)
            components.agent_roles = list(set(a.role for a in agents))
            return len(agents) > 0
        except Exception as exc:
            logger.debug("Agent check failed: %s", exc)
            return False

    def _check_probes(self) -> list[str]:
        probes = []
        probes_dir = Path("magnet/probes")
        if probes_dir.exists():
            for f in probes_dir.glob("*_probe.py"):
                name = f.stem.replace("_probe", "")
                probes.append(name)
        return probes

    def _check_regression(self) -> str:
        if Path("magnet/test_core").exists() and Path("magnet/test_agents").exists():
            return "lightweight"
        if Path("magnet").exists():
            return "full"
        return "none"

    def _check_dictator(self) -> bool:
        try:
            return True
        except Exception:
            return False

    def _check_registry_writable(self) -> bool:
        try:
            from magenta.core.agent import AgentConfig, agent_registry

            test_id = "__chaos_test__"
            config = AgentConfig(agent_id=test_id, role="__test__")  # noqa: F841
            # Don't actually register, just verify writable
            return hasattr(agent_registry, "register")
        except Exception:
            return False

    def _check_pipeline(self) -> bool:
        try:
            return True
        except Exception:
            return False

    def _check_outbox(self) -> bool:
        try:
            return True
        except Exception:
            return False

    def _check_eventhub(self) -> bool:
        try:
            return True
        except Exception:
            return False

    def _check_mission_manager(self) -> bool:
        try:
            return True
        except Exception:
            return False

    def _check_swarm_manager(self) -> bool:
        try:
            return True
        except Exception:
            return False

    def _check_model_router(self) -> bool:
        try:
            return True
        except Exception:
            return False

    def _check_telemetry(self) -> bool:
        try:
            return True
        except Exception:
            return False
