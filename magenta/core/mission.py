"""Mission lifecycle state machine."""

from __future__ import annotations

import logging
from datetime import datetime

from magenta.core.models import AgentConfig, Mission, MissionStatus, Playbook
from magenta.core.redis_manager import redis_manager
from magenta.exceptions import MissionError, MissionNotFoundError

logger = logging.getLogger(__name__)

_VALID_TRANSITIONS: dict[MissionStatus, set[MissionStatus]] = {
    MissionStatus.created: {
        MissionStatus.scoped, MissionStatus.executing, MissionStatus.cancelled,
    },
    MissionStatus.scoped: {
        MissionStatus.assigned, MissionStatus.executing, MissionStatus.cancelled,
    },
    MissionStatus.assigned: {MissionStatus.executing, MissionStatus.cancelled},
    MissionStatus.executing: {
        MissionStatus.review, MissionStatus.completed,
        MissionStatus.failed, MissionStatus.escalated, MissionStatus.cancelled,
    },
    MissionStatus.review: {
        MissionStatus.completed, MissionStatus.failed, MissionStatus.escalated,
    },
    MissionStatus.escalated: {
        MissionStatus.completed, MissionStatus.failed, MissionStatus.cancelled,
    },
    MissionStatus.completed: set(),
    MissionStatus.failed: set(),
    MissionStatus.cancelled: set(),
}


class MissionManager:
    """Manages mission lifecycle: create → scope → assign → execute → complete.

    Supports Redis-backed persistence via shared RedisManager.
    Falls back to in-memory storage if Redis is unavailable.
    """

    def __init__(self):
        self._missions: dict[str, Mission] = {}

    async def _ensure_redis(self) -> None:
        """Initialize shared RedisManager. Called once during server startup."""
        await redis_manager.initialize()

    async def _save_mission(self, mission: Mission) -> None:
        """Persist mission to Redis via shared manager."""
        await redis_manager.save_json(
            f"mission:{mission.mission_id}",
            mission.model_dump(mode="json"),
        )

    async def _remove_mission(self, mission_id: str) -> None:
        """Remove mission from Redis via shared manager."""
        await redis_manager.remove(f"mission:{mission_id}")

    async def _load_from_redis(self) -> None:
        """Load missions from Redis via shared manager."""
        keys = await redis_manager.keys("mission:*")
        for key in keys:
            data = await redis_manager.load_json(key)
            if data:
                mission = Mission(**data)
                self._missions[mission.mission_id] = mission
        logger.info("Loaded %d missions from Redis", len(keys))

    def create(self, alert_id: str, source_system: str,
               playbook: Playbook | None = None,
               description: str = "") -> Mission:
        mission = Mission(
            alert_id=alert_id,
            source_system=source_system,
            playbook_id=playbook.name if playbook else "",
            playbook_version=playbook.version if playbook else "",
            description=description or f"Mission for {source_system} alert {alert_id}",
            status=MissionStatus.created,
        )
        self._missions[mission.mission_id] = mission
        return mission

    def get(self, mission_id: str) -> Mission:
        mission = self._missions.get(mission_id)
        if not mission:
            raise MissionNotFoundError(f"Mission {mission_id} not found")
        return mission

    def list(self, status: str | None = None) -> list[Mission]:
        missions = list(self._missions.values())
        if status:
            try:
                s = MissionStatus(status)
                missions = [m for m in missions if m.status == s]
            except ValueError:
                pass
        return sorted(missions, key=lambda m: m.created_at, reverse=True)

    def list_active(self) -> list[Mission]:
        """Return missions in non-terminal states."""
        terminal = {MissionStatus.completed, MissionStatus.failed, MissionStatus.cancelled}
        return [
            m for m in self._missions.values()
            if m.status not in terminal
        ]

    def update_status(self, mission_id: str, status: MissionStatus) -> Mission:
        mission = self.get(mission_id)
        allowed = _VALID_TRANSITIONS.get(mission.status, set())
        if status not in allowed:
            raise MissionError(
                f"Invalid transition: {mission.status.value} → {status.value}"
            )
        mission.status = status
        mission.updated_at = datetime.utcnow()
        if status in (MissionStatus.completed, MissionStatus.failed, MissionStatus.cancelled):
            mission.completed_at = datetime.utcnow()
        return mission

    def assign_agent(self, mission_id: str, agent: AgentConfig) -> Mission:
        mission = self.get(mission_id)
        if agent not in mission.team:
            mission.team.append(agent)
        mission.updated_at = datetime.utcnow()
        return mission

    def add_task(self, mission_id: str, task: dict) -> Mission:
        mission = self.get(mission_id)
        mission.tasks.append(task)
        mission.updated_at = datetime.utcnow()
        return mission

    def update_bundle(self, mission_id: str, bundle: dict) -> Mission:
        mission = self.get(mission_id)
        mission.artifact_bundle.update(bundle)
        mission.updated_at = datetime.utcnow()
        return mission

    def delete(self, mission_id: str) -> None:
        if mission_id not in self._missions:
            raise MissionNotFoundError(f"Mission {mission_id} not found")
        mission = self._missions[mission_id]
        terminal = {MissionStatus.completed, MissionStatus.failed, MissionStatus.cancelled}
        if mission.status not in terminal:
            raise MissionError(
                f"Cannot delete mission in {mission.status.value} state"
            )
        del self._missions[mission_id]

    def active_count(self) -> int:
        return len(self.list_active())


mission_manager = MissionManager()
