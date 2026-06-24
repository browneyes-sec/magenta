"""Dictator — super-agent orchestrator.

The Dictator sits at the top of the agent hierarchy, commanding all
framework resources: agents, probes, CLI, data mesh, API, and core.
It issues directives, evaluates policies, manages oversight, and
can override any subsystem at runtime.
"""

from datetime import datetime
from typing import Any

from magenta.agents.base import LLMAgent
from magenta.agents.manager import SwarmManagerAgent
from magenta.config import settings
from magenta.core.agent import BaseAgent, agent_registry
from magenta.core.mission import mission_manager
from magenta.core.models import (
    AgentConfig,
    Mission,
    MissionStatus,
)
from magenta.core.swarm import swarm_manager
from magenta.dictator.directives import (
    Directive,
    DirectivePriority,
    DirectiveType,
    issue_directive,
)
from magenta.dictator.policies import OrchestrationPolicy, policy_engine
from magenta.dictator.state import DictatorStatus, dictator_state
from magenta.exceptions import AgentError


class DictatorAgent(LLMAgent):
    """Super-agent that commands the entire Magenta ASOAR framework.

    The Dictator:
      - Commissions and decommissions agents on demand
      - Evaluates orchestration policies per mission
      - Issues directives to agents, probes, and subsystems
      - Maintains real-time oversight of all active missions
      - Can override teaming structures, inject probes, halt missions
    """
    sensitivity_level = "high"
    task_type = "command"

    def __init__(self, config: AgentConfig | None = None):
        if config is None:
            config = AgentConfig(
                agent_id="dictator-001",
                role="dictator",
                model_provider=settings.models.default_provider,
                model_name=settings.models.default_model,
                instructions="""You are the Dictator — the super-agent orchestrator of the Magenta ASOAR framework.
You have executive access to all agents, probes, data mesh, CLI, API, and core systems.
Your role is to command missions, issue directives, enforce policies, and maintain
oversight of all active operations. You can deploy or recall any agent, override
teaming structures, inject probes, halt missions, and escalate incidents.""",
                tools=["deploy_agent", "recall_agent", "issue_directive",
                       "override_teaming", "inject_probe", "halt_mission",
                       "escalate", "run_playbook", "query_mesh"],
                max_concurrent_tasks=10,
                max_turns=50,
                risk_tolerance=0.9,
            )
        super().__init__(config)
        self.status = DictatorStatus.idle

    # ── Core Process ──────────────────────────────────────────────

    async def _process_impl(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        """Process a mission: evaluate policies, deploy agents, issue directives."""

        # 1. Evaluate orchestration policies
        policy_config = policy_engine.evaluate(mission)
        teaming = policy_config["teaming"]
        probe_config = policy_config.get("probes", {})
        auto_approve = policy_config.get("auto_approve", True)

        # 2. Track mission oversight
        dictator_state.track_mission(
            mission_id=mission.mission_id,
            teaming=teaming,
            agents=len(mission.team),
        )

        # 3. Issue deployment directive
        deploy_directive = issue_directive(
            dtype=DirectiveType.deploy_agent,
            target="swarm_manager",
            mission_id=mission.mission_id,
            payload={
                "teaming": teaming,
                "auto_approve": auto_approve,
                "probes": probe_config,
            },
            reason=f"Policy evaluation: {teaming} teaming for severity {mission.severity.value}",
        )

        # 4. Delegate to Swarm Manager
        managers = agent_registry.get_by_role("swarm_manager")
        if managers:
            manager = managers[0]
            result = await manager.run_mission(mission)

            # 5. Inject probes per policy
            if probe_config.get("all") or probe_config.get("triage"):
                await self._inject_probes(mission)

            # 6. Complete oversight
            dictator_state.complete_mission(mission.mission_id)
            self.status = DictatorStatus.reviewing

            return {
                "dictator": self.agent_id,
                "mission_id": mission.mission_id,
                "teaming": teaming,
                "policy": policy_config,
                "directives_issued": len(dictator_state.directive_log),
                "mission_result": result,
                "status": "completed",
            }

        raise AgentError("No Swarm Manager agent registered")

    # ── Directives ────────────────────────────────────────────────

    async def issue_directive(
        self,
        dtype: DirectiveType,
        target: str,
        mission_id: str | None = None,
        payload: dict | None = None,
        reason: str = "",
    ) -> Directive:
        """Issue a framework directive."""
        return issue_directive(dtype, target, mission_id, payload, reason)

    async def halt_mission(self, mission_id: str, reason: str = "Manual override") -> dict:
        """Immediately halt a running mission."""
        directive = issue_directive(
            dtype=DirectiveType.halt_mission,
            target="orchestration_engine",
            mission_id=mission_id,
            payload={"reason": reason},
            reason=reason,
            priority=DirectivePriority.critical,
        )
        try:
            await swarm_manager.cancel_mission(mission_id)
        except Exception:
            pass
        dictator_state.complete_mission(mission_id)
        return {"directive_id": directive.directive_id, "status": "halted"}

    async def escalate_mission(self, mission_id: str, reason: str = "") -> dict:
        """Escalate a mission to human operators."""
        directive = issue_directive(
            dtype=DirectiveType.escalate,
            target="human_operator",
            mission_id=mission_id,
            payload={
                "reason": reason or "Dictator escalation",
            },
            reason="Mission escalated per Dictator directive",
            priority=DirectivePriority.high,
        )
        try:
            mission = mission_manager.get(mission_id)
            mission_manager.update_status(mission_id, MissionStatus.escalated)
        except Exception:
            pass
        return {"directive_id": directive.directive_id, "status": "escalated"}

    # ── Agent Management ──────────────────────────────────────────

    async def deploy_agent(self, role: str, **kwargs) -> BaseAgent:
        """Deploy a new agent into the registry."""
        cfg = AgentConfig(
            agent_id=f"{role}-{datetime.utcnow().strftime('%H%M%S')}",
            role=role,
            **kwargs,
        )
        from magenta.agents.triage import TriageAgent

        role_map: dict[str, type[BaseAgent]] = {
            "triage": TriageAgent,
            "swarm_manager": SwarmManagerAgent,
        }
        agent_cls = role_map.get(role)
        if agent_cls is None:
            # Fallback: create a lightweight agent with a no-op process
            class _GenericAgent(BaseAgent):
                async def process(self, mission, context):
                    return {"role": self.role, "status": "deployed"}
            agent_cls = _GenericAgent

        agent = agent_cls(cfg)
        await agent.initialize()
        agent_registry.register(agent)

        issue_directive(
            dtype=DirectiveType.deploy_agent,
            target=role,
            payload={"agent_id": cfg.agent_id},
            reason=f"Dictator deployed {role} agent",
        )
        return agent

    async def recall_agent(self, agent_id: str) -> bool:
        """Recall (unregister) an agent."""
        agent = agent_registry.get_by_id(agent_id)
        if agent:
            agent_registry.unregister(agent_id)
            issue_directive(
                dtype=DirectiveType.recall_agent,
                target=agent_id,
                reason=f"Dictator recalled agent {agent_id}",
            )
            return True
        return False

    async def override_teaming(self, mission_id: str, structure: str) -> dict:
        """Override the teaming structure for an active mission."""
        directive = issue_directive(
            dtype=DirectiveType.override_teaming,
            target="swarm_manager",
            mission_id=mission_id,
            payload={"teaming": structure},
            reason=f"Dictator override to {structure} teaming",
            priority=DirectivePriority.high,
        )
        oversight = dictator_state.active_missions.get(mission_id)
        if oversight:
            oversight.teaming_structure = structure
        return {"directive_id": directive.directive_id, "teaming": structure}

    # ── Probe Management ──────────────────────────────────────────

    async def _inject_probes(self, mission: Mission) -> None:
        """Inject probe points per policy configuration."""
        for task in mission.tasks:
            issue_directive(
                dtype=DirectiveType.inject_probe,
                target=task.get("role", "unknown"),
                mission_id=mission.mission_id,
                payload={
                    "task_id": task["task_id"],
                    "task_type": task["task_type"],
                    "probe_points": ["pre_process", "post_process", "tool_call"],
                },
                reason="Policy-required probe injection",
            )
        oversight = dictator_state.active_missions.get(mission.mission_id)
        if oversight:
            oversight.probe_count = len(mission.tasks)

    async def promote_probe(self, probe_name: str, guard: bool = False) -> dict:
        """Promote a probe to a guard (enforcement point)."""
        directive = issue_directive(
            dtype=DirectiveType.promote_probe,
            target="magnet",
            payload={"probe": probe_name, "guard": guard},
            reason=f"Promote probe {probe_name}" + (" to guard" if guard else ""),
        )
        return {"directive_id": directive.directive_id, "probe": probe_name}

    # ── Policy Management ─────────────────────────────────────────

    async def apply_policy_override(self, policy: OrchestrationPolicy) -> dict:
        """Apply a temporary policy override."""
        await policy_engine.set_override(policy)
        issue_directive(
            dtype=DirectiveType.policy_override,
            target="policy_engine",
            payload={"policy": policy.name, "rules": policy.rules},
            reason=f"Dictator policy override: {policy.name}",
            priority=DirectivePriority.high,
        )
        return {"status": "override_applied", "policy": policy.name}

    async def clear_policy_overrides(self) -> dict:
        """Clear all active policy overrides."""
        await policy_engine.clear_overrides()
        return {"status": "overrides_cleared"}

    # ── Oversight ─────────────────────────────────────────────────

    async def get_oversight_board(self) -> dict[str, Any]:
        """Return the full oversight board of all missions."""
        return {
            "dictator_status": self.status.value if hasattr(self.status, "value") else self.status,
            "active_missions": {
                mid: oversight.model_dump()
                for mid, oversight in dictator_state.active_missions.items()
            },
            "completed_count": len(dictator_state.completed_missions),
            "total_directives": len(dictator_state.directive_log),
            "uptime": (datetime.utcnow() - dictator_state.started_at).total_seconds(),
        }

    async def get_mission_oversight(self, mission_id: str) -> dict | None:
        """Get oversight details for a specific mission."""
        oversight = dictator_state.active_missions.get(mission_id)
        if oversight:
            return oversight.model_dump()
        if mission_id in dictator_state.completed_missions:
            return {"mission_id": mission_id, "status": "completed"}
        return None

    async def get_directive_log(self, limit: int = 50) -> list[dict]:
        """Return the last N directives issued."""
        return dictator_state.directive_log[-limit:]

    # ── System Commands ───────────────────────────────────────────

    async def system_command(self, command: str, params: dict[str, Any]) -> dict:
        """Execute a system-level command against framework resources."""
        directive = issue_directive(
            dtype=DirectiveType.system_command,
            target="framework",
            payload={"command": command, "params": params},
            reason=f"Dictator system command: {command}",
            priority=DirectivePriority.critical,
        )
        return {"directive_id": directive.directive_id, "command": command, "executed": True}

    async def get_framework_status(self) -> dict[str, Any]:
        """Return comprehensive framework status."""
        return {
        "dictator": {
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "turn_count": self.turn_count,
        },
            "registry": {
                "agents_by_role": agent_registry.counts,
                "total_agents": len(agent_registry.all_agents()),
            },
            "missions": {
                "active": len(dictator_state.active_missions),
                "completed": len(dictator_state.completed_missions),
                "directives": len(dictator_state.directive_log),
            },
            "policies": {
                "active": len(policy_engine._policies),
                "overrides": len(policy_engine._overrides),
            },
            "uptime_seconds": (datetime.utcnow() - dictator_state.started_at).total_seconds(),
        }


dictator = DictatorAgent()
