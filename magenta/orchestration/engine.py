"""Orchestration engine — DAG-based mission executor."""

import asyncio

from magenta.core.mission import mission_manager
from magenta.core.models import Mission, MissionStatus
from magenta.core.swarm import swarm_manager
from magenta.orchestration.dag_executor import dag_executor


class OrchestrationEngine:
    """Main orchestration engine that runs missions as DAGs."""

    def __init__(self):
        self._running: dict[str, asyncio.Task] = {}

    async def start_mission(self, mission_id: str) -> Mission:
        """Start executing a mission through the DAG executor."""
        mission = mission_manager.get(mission_id)
        mission_manager.update_status(mission_id, MissionStatus.executing)

        # Run mission in background task using DAG executor
        task = asyncio.create_task(self._run_mission(mission_id))
        self._running[mission_id] = task

        return mission

    async def _run_mission(self, mission_id: str) -> dict:
        """Background task that runs the mission via DAG executor."""
        try:
            result = await dag_executor.execute_mission(mission_id)
            return result
        except Exception:
            mission_manager.update_status(mission_id, MissionStatus.failed)
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
        """Get mission execution logs."""
        mission = mission_manager.get(mission_id)
        return [
            {
                "timestamp": mission.created_at.isoformat(),
                "level": "INFO",
                "message": "Mission created",
            },
            {
                "timestamp": mission.updated_at.isoformat(),
                "level": "INFO",
                "message": f"Status: {mission.status.value}",
            },
        ]

    def is_running(self, mission_id: str) -> bool:
        return mission_id in self._running and not self._running[mission_id].done()


orchestration_engine = OrchestrationEngine()
