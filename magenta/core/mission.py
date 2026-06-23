"""Mission lifecycle state machine."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from magenta.core.models import AgentConfig, Mission, MissionStatus, Playbook
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

    Supports Redis-backed persistence when MAGENTA_REDIS_PERSISTENCE=true.
    Falls back to in-memory storage if Redis is unavailable.
    """

    def __init__(self, redis_url: str = ""):
        self._missions: dict[str, Mission] = {}
        self._redis_url = redis_url or os.getenv(
            "MAGENTA_REDIS_URL", "redis://localhost:6379/0"
        )
        self._redis = None
        self._persistence_enabled = os.getenv(
            "MAGENTA_REDIS_PERSISTENCE", "false"
        ).lower() == "true"

    async def _ensure_redis(self):
        if self._redis is not None:
            return self._redis
        if not self._persistence_enabled:
            return False
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(self._redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
            await self._load_from_redis()
        except Exception as exc:
            logger.debug("Redis unavailable for MissionManager, using in-memory: %s", exc)
            self._redis = False
        return self._redis

    async def _load_from_redis(self):
        if not self._redis:
            return
        try:
            keys = await self._redis.keys("mission:*")
            for key in keys:
                data = await self._redis.get(key)
                if data:
                    mission_data = json.loads(data)
                    mission = Mission(**mission_data)
                    self._missions[mission.mission_id] = mission
            logger.info("Loaded %d missions from Redis", len(keys))
        except Exception as exc:
            logger.warning("Failed to load missions from Redis: %s", exc)

    async def _save_mission(self, mission: Mission):
        if not self._persistence_enabled or not self._redis:
            return
        try:
            key = f"mission:{mission.mission_id}"
            await self._redis.set(key, mission.model_dump_json())
        except Exception as exc:
            logger.debug("Redis save failed for mission %s: %s", mission.mission_id, exc)

    async def _remove_mission(self, mission_id: str):
        if not self._persistence_enabled or not self._redis:
            return
        try:
            await self._redis.delete(f"mission:{mission_id}")
        except Exception:
            pass

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
