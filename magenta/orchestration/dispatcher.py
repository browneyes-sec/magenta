"""Task dispatcher — routes tasks to available agents."""

from typing import Any, Optional

from magenta.core.models import Mission, AgentConfig
from magenta.core.agent import agent_registry
from magenta.exceptions import AgentError


class Dispatcher:
    """Dispatches tasks to agents based on role, load, and availability."""

    async def dispatch(self, task: dict, mission: Mission) -> Optional[str]:
        """Dispatch a task to an available agent. Returns agent_id or None."""
        role = task.get("role")
        if not role:
            raise AgentError(f"Task {task.get('task_id')} has no role")

        agents = agent_registry.get_available(role)
        if not agents:
            return None

        # Pick least-loaded agent
        agent = min(agents, key=lambda a: a.turn_count)
        task["agent_id"] = agent.agent_id
        task["status"] = "assigned"
        agent.current_mission = mission
        agent.status = "ready"

        return agent.agent_id

    async def dispatch_all(self, tasks: list[dict], mission: Mission) -> list[dict]:
        """Dispatch all pending tasks."""
        results = []
        for task in tasks:
            if task.get("status") == "pending":
                agent_id = await self.dispatch(task, mission)
                results.append({
                    "task_id": task["task_id"],
                    "agent_id": agent_id or "unassigned",
                    "status": "assigned" if agent_id else "unassigned",
                })
        return results

    async def retry_failed(self, task: dict, mission: Mission) -> Optional[str]:
        """Retry a failed task with a different agent."""
        return await self.dispatch(task, mission)


dispatcher = Dispatcher()
