"""Mission lifecycle state machine."""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from magenta.core.models import (
    Mission, MissionStatus, AgentConfig, Playbook
)
from magenta.exceptions import MissionError, MissionNotFoundError


class MissionManager:
    """Manages mission lifecycle: create → scope → assign → execute → complete."""

    def __init__(self):
        self._missions: dict[str, Mission] = {}

    def create(self, alert_id: str, source_system: str,
               playbook: Optional[Playbook] = None,
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

    def list(self, status: Optional[str] = None) -> list[Mission]:
        missions = list(self._missions.values())
        if status:
            try:
                s = MissionStatus(status)
                missions = [m for m in missions if m.status == s]
            except ValueError:
                pass
        return sorted(missions, key=lambda m: m.created_at, reverse=True)

    def update_status(self, mission_id: str, status: MissionStatus) -> Mission:
        mission = self.get(mission_id)
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
        del self._missions[mission_id]

    def active_count(self) -> int:
        return sum(
            1 for m in self._missions.values()
            if m.status in (MissionStatus.created, MissionStatus.assigned, MissionStatus.executing)
        )


mission_manager = MissionManager()
