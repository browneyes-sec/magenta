"""Swarm Manager Agent — orchestrates multi-agent missions."""

from typing import Any
from datetime import datetime

from magenta.agents.base import LLMAgent
from magenta.core.models import (
    Mission, MissionStatus, AgentConfig, SeverityLevel, ActionStatus
)
from magenta.core.swarm import swarm_manager
from magenta.core.mission import mission_manager
from magenta.core.agent import agent_registry


class SwarmManagerAgent(LLMAgent):
    """Meta-agent that orchestrates the multi-agent swarm for a mission."""
    sensitivity_level = "medium"
    task_type = "orchestrate"

    def __init__(self, config: AgentConfig):
        config.instructions = config.instructions or """You are the Swarm Manager — the orchestrator of the Magenta multi-agent system.
Your job is to decompose security incidents into tasks, assign agents,
monitor progress, handle failures, and ensure mission completion."""
        super().__init__(config)

    async def process(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        self.status = "executing"
        self.turn_count += 1

        # Decompose mission into tasks
        tasks = await swarm_manager.decompose_mission(mission)
        mission.tasks = tasks

        # Assign agents
        await swarm_manager.assign_agents(mission, tasks)

        # Select teaming structure
        structure = swarm_manager.get_team_structure(mission)

        result = {
            "agent": self.role,
            "mission_id": mission.mission_id,
            "tasks": len(tasks),
            "agents_assigned": len(mission.team),
            "teaming_structure": structure,
            "severity": mission.severity.value,
            "risk_score": mission.risk_score,
        }

        mission_manager.update_status(mission.mission_id, MissionStatus.executing)
        await self.log_activity(mission, "orchestrate", ActionStatus.succeeded)
        self.status = "done"
        return result

    async def run_mission(self, mission: Mission) -> dict[str, Any]:
        """Run a full mission lifecycle through the swarm."""
        result = await self.process(mission, {})

        # Execute each agent in sequence (simplified pipeline)
        for task in mission.tasks:
            agent_id = task.get("agent_id")
            if not agent_id:
                continue

            agent = agent_registry.get_by_id(agent_id)
            if not agent:
                continue

            try:
                task_result = await agent.process(mission, result)
                result[f"task_{task['task_id']}"] = task_result
            except Exception as e:
                result[f"task_{task['task_id']}_error"] = str(e)

        mission_manager.update_status(mission.mission_id, MissionStatus.completed)
        return result
