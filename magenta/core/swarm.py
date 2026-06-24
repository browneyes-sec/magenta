"""Swarm management: assembly, task decomposition, delegation."""

from __future__ import annotations

from magenta.core.agent import agent_registry
from magenta.core.mission import mission_manager
from magenta.core.models import Mission, MissionStatus, SeverityLevel


class SwarmManager:
    """
    Orchestrates multi-agent swarms: decomposes alerts into tasks,
    assigns agents, monitors progress, handles failures.
    """

    def __init__(self):
        self._assignments: dict[str, dict[str, str]] = {}  # mission_id -> {task_id: agent_id}

    async def decompose_mission(self, mission: Mission) -> list[dict]:
        """Decompose an alert into a set of tasks."""
        severity = mission.severity
        tasks = []

        # Base: triage + report are always needed
        tasks.append({
            "task_id": f"triage-{mission.mission_id[:8]}",
            "task_type": "triage",
            "role": "triage",
            "status": "pending",
            "dependencies": [],
        })

        tasks.append({
            "task_id": f"report-{mission.mission_id[:8]}",
            "task_type": "report",
            "role": "report",
            "status": "pending",
            "dependencies": [],
        })

        # Severity >= 3 gets enrichment
        if severity.value >= SeverityLevel.medium.value:
            tasks.append({
                "task_id": f"enrich-{mission.mission_id[:8]}",
                "task_type": "enrich",
                "role": "enrich",
                "status": "pending",
                "dependencies": [f"triage-{mission.mission_id[:8]}"],
            })

        # Severity >= 4 gets containment and investigation
        if severity.value >= SeverityLevel.high.value:
            tasks.append({
                "task_id": f"contain-{mission.mission_id[:8]}",
                "task_type": "contain",
                "role": "contain",
                "status": "pending",
                "dependencies": [f"enrich-{mission.mission_id[:8]}"],
            })
            tasks.append({
                "task_id": f"investigate-{mission.mission_id[:8]}",
                "task_type": "investigate",
                "role": "investigate",
                "status": "pending",
                "dependencies": [f"enrich-{mission.mission_id[:8]}"],
            })

        # Severe or critical gets compliance review
        if severity.value >= SeverityLevel.high.value:
            tasks.append({
                "task_id": f"compliance-{mission.mission_id[:8]}",
                "task_type": "compliance",
                "role": "compliance",
                "status": "pending",
                "dependencies": [f"contain-{mission.mission_id[:8]}"] if severity.value >= SeverityLevel.high.value else [],
            })

        return tasks

    async def assign_agents(self, mission: Mission, tasks: list[dict]) -> dict[str, str]:
        """Assign available agents to tasks based on role."""
        assignment = {}

        for task in tasks:
            role = task["role"]
            available = agent_registry.get_available(role)

            if available:
                agent = available[0]
                agent.current_mission = mission
                agent.status = "ready"
                task["agent_id"] = agent.agent_id
                assignment[task["task_id"]] = agent.agent_id
                mission_manager.assign_agent(mission.mission_id, agent.config)
            else:
                task["status"] = "unassigned"

        mission.tasks = tasks
        self._assignments[mission.mission_id] = assignment
        return assignment

    def get_team_structure(self, mission: Mission) -> str:
        """Determine teaming structure based on mission characteristics."""
        severity = mission.severity
        risk = mission.risk_score

        if risk > 70:
            return "referee"
        if severity.value >= SeverityLevel.critical.value:
            return "supervisor"
        if severity.value <= SeverityLevel.low.value:
            return "pipeline"
        return "supervisor"

    async def execute_mission(self, mission_id: str) -> None:
        """Execute a mission through the swarm lifecycle."""
        mission = mission_manager.get(mission_id)

        mission_manager.update_status(mission_id, MissionStatus.scoped)
        tasks = await self.decompose_mission(mission)
        await self.assign_agents(mission, tasks)

        mission_manager.update_status(mission_id, MissionStatus.assigned)

    async def cancel_mission(self, mission_id: str) -> None:
        """Cancel a running mission."""
        mission = mission_manager.get(mission_id)
        for agent_config in mission.team:
            agent = agent_registry.get_by_id(agent_config.agent_id)
            if agent:
                agent.reset()
        mission_manager.update_status(mission_id, MissionStatus.cancelled)

    def get_mission_agents(self, mission_id: str) -> list[dict]:
        """Get agent assignments for a mission."""
        mission = mission_manager.get(mission_id)
        result = []
        for task in mission.tasks:
            agent_id = task.get("agent_id", "")
            agent = agent_registry.get_by_id(agent_id)
            result.append({
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "role": task["role"],
                "agent_id": agent_id,
                "agent_role": agent.role if agent else "unknown",
                "status": agent.status.value if agent else "unknown",
            })
        return result

    @property
    def active_assignments(self) -> dict[str, dict[str, str]]:
        return self._assignments


swarm_manager = SwarmManager()
