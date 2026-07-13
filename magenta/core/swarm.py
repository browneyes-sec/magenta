"""Swarm management: assembly, task decomposition, delegation."""

from __future__ import annotations
from typing import Any, Optional
import asyncio
import logging

from magenta.core.models import (
    Mission, MissionStatus, AgentConfig, SeverityLevel, BlastRadius, ActionStatus
)
from magenta.core.agent import agent_registry, BaseAgent
from magenta.core.mission import mission_manager
from magenta.exceptions import AgentError

logger = logging.getLogger(__name__)


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

    async def execute_mission(self, mission_id: str) -> dict[str, Any]:
        """Execute a mission through the swarm lifecycle with parallel task execution.

        Execution strategy:
            1. Decompose mission into tasks with dependency declarations
            2. Assign agents to tasks
            3. Execute independent tasks (no dependencies) concurrently
            4. Execute dependent tasks in topological resolution order
            5. Aggregate results and mark mission complete

        Returns:
            Dict with task_results keyed by task_id.
        """
        mission = mission_manager.get(mission_id)
        mission_manager.update_status(mission_id, MissionStatus.scoped)

        tasks = await self.decompose_mission(mission)
        await self.assign_agents(mission, tasks)
        mission_manager.update_status(mission_id, MissionStatus.assigned)

        # ─── Phase 1: Execute independent tasks concurrently ─────────────
        task_context: dict[str, Any] = {}
        task_results: dict[str, Any] = {}
        task_map = {t["task_id"]: t for t in tasks}
        executed: set[str] = set()

        independent = [t for t in tasks if not t.get("dependencies")]
        if independent:
            logger.info(
                "Swarm[%s]: executing %d independent tasks concurrently",
                mission_id[:8],
                len(independent),
            )
            results = await asyncio.gather(
                *[self._execute_single_task(t, mission, task_context)
                  for t in independent],
                return_exceptions=True,
            )
            for task, result in zip(independent, results):
                tid = task["task_id"]
                if isinstance(result, Exception):
                    task_results[tid] = {"status": "failed", "error": str(result)}
                    logger.error("Swarm[%s]: task %s failed: %s", mission_id[:8], tid, result)
                else:
                    task_results[tid] = {"status": "completed", "result": result}
                    if isinstance(result, dict):
                        task_context.update({f"{tid}.{k}": v for k, v in result.items()})
                executed.add(tid)

        # ─── Phase 2: Execute dependent tasks in topological order ───────
        remaining = [t for t in tasks if t["task_id"] not in executed]
        while remaining:
            # Find tasks whose dependencies are all satisfied
            ready = [
                t for t in remaining
                if all(dep in executed for dep in t.get("dependencies", []))
            ]
            if not ready:
                missing = []
                for t in remaining:
                    for dep in t.get("dependencies", []):
                        if dep not in executed:
                            missing.append(f"{t['task_id']}⭢{dep}")
                raise AgentError(
                    f"Swarm[{mission_id[:8]}]: circular or missing dependencies: "
                    f"{', '.join(missing)}"
                )

            logger.info(
                "Swarm[%s]: executing %d dependent tasks concurrently",
                mission_id[:8],
                len(ready),
            )
            results = await asyncio.gather(
                *[self._execute_single_task(t, mission, task_context)
                  for t in ready],
                return_exceptions=True,
            )
            for task, result in zip(ready, results):
                tid = task["task_id"]
                if isinstance(result, Exception):
                    task_results[tid] = {"status": "failed", "error": str(result)}
                    logger.error("Swarm[%s]: task %s failed: %s", mission_id[:8], tid, result)
                else:
                    task_results[tid] = {"status": "completed", "result": result}
                    if isinstance(result, dict):
                        task_context.update({f"{tid}.{k}": v for k, v in result.items()})
                executed.add(tid)

            # Update remaining
            remaining = [t for t in tasks if t["task_id"] not in executed]

        mission_manager.update_status(mission_id, MissionStatus.completed)
        logger.info(
            "Swarm[%s]: mission complete — %d tasks executed",
            mission_id[:8],
            len(executed),
        )
        return {"task_results": task_results}

    async def _execute_single_task(
        self,
        task: dict,
        mission: Mission,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single task through its assigned agent.

        Args:
            task: Task descriptor with task_id, role, agent_id.
            mission: The parent mission.
            context: Accumulated context from prior task executions.

        Returns:
            Result dict from the agent's process() method.
        """
        agent_id = task.get("agent_id")
        if not agent_id:
            raise AgentError(f"Task {task['task_id']} has no assigned agent")

        agent = agent_registry.get_by_id(agent_id)
        if not agent:
            raise AgentError(
                f"Task {task['task_id']}: agent {agent_id} not found in registry"
            )

        logger.debug(
            "Swarm: executing task %s on agent %s (%s)",
            task["task_id"],
            agent_id,
            agent.role,
        )
        task["status"] = "executing"
        result = await agent.process(mission, context)
        task["status"] = "completed"
        return result

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
