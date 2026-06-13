"""Orchestration engine — pipeline runner for mission execution."""

from typing import Any, Optional
from datetime import datetime
import asyncio

from magenta.core.models import Mission, MissionStatus
from magenta.core.mission import mission_manager
from magenta.core.swarm import swarm_manager
from magenta.core.agent import agent_registry
from magenta.agents.manager import SwarmManagerAgent
from magenta.agents.base import LLMAgent
from magenta.exceptions import MissionError


class OrchestrationEngine:
    """Main orchestration engine that runs missions through the swarm."""

    def __init__(self):
        self._running: dict[str, asyncio.Task] = {}

    async def start_mission(self, mission_id: str) -> Mission:
        """Start executing a mission through the swarm."""
        mission = mission_manager.get(mission_id)

        # Get or create Swarm Manager
        managers = agent_registry.get_by_role("swarm_manager")
        if not managers:
            raise MissionError("No Swarm Manager agent registered")

        manager = managers[0]
        mission_manager.update_status(mission_id, MissionStatus.executing)

        # Run mission in background task
        task = asyncio.create_task(self._run_mission(manager, mission))
        self._running[mission_id] = task

        return mission

    async def _run_mission(self, manager: SwarmManagerAgent, mission: Mission) -> dict:
        """Background task that runs the full mission."""
        try:
            result = await manager.run_mission(mission)
            mission_manager.update_status(mission.mission_id, MissionStatus.completed)
            return result
        except Exception as e:
            mission_manager.update_status(mission.mission_id, MissionStatus.failed)
            raise

    async def stop_mission(self, mission_id: str) -> None:
        """Stop a running mission."""
        task = self._running.pop(mission_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await swarm_manager.cancel_mission(mission_id)

    async def get_mission_logs(self, mission_id: str, tail: int = 100) -> list[dict]:
        """Get mission execution logs (stub — data layer integration)."""
        mission = mission_manager.get(mission_id)
        return [
            {"timestamp": mission.created_at.isoformat(), "level": "INFO", "message": "Mission created"},
            {"timestamp": mission.updated_at.isoformat(), "level": "INFO", "message": f"Status: {mission.status.value}"},
        ]

    def is_running(self, mission_id: str) -> bool:
        return mission_id in self._running and not self._running[mission_id].done()


orchestration_engine = OrchestrationEngine()
