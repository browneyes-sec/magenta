"""Dictator global state — oversight board, mission registry, policy store."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class DictatorStatus(str, Enum):
    idle = "idle"
    commanding = "commanding"
    reviewing = "reviewing"
    override = "override"
    error = "error"


class MissionOversight(BaseModel):
    """Runtime oversight record for a single mission under Dictator command."""

    mission_id: str
    status: str = "active"
    teaming_structure: str = "supervisor"
    agent_count: int = 0
    task_count: int = 0
    probe_count: int = 0
    directive_count: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    annotations: dict[str, Any] = Field(default_factory=dict)


class DictatorState(BaseModel):
    """Global state of the Dictator super-agent."""

    status: DictatorStatus = DictatorStatus.idle
    active_missions: dict[str, MissionOversight] = Field(default_factory=dict)
    completed_missions: list[str] = Field(default_factory=list)
    directive_log: list[dict] = Field(default_factory=list)
    policy_overrides: dict[str, Any] = Field(default_factory=dict)
    uptime: float = 0.0
    started_at: datetime = Field(default_factory=datetime.utcnow)

    def track_mission(self, mission_id: str, teaming: str = "supervisor", agents: int = 0) -> None:
        oversight = MissionOversight(
            mission_id=mission_id,
            teaming_structure=teaming,
            agent_count=agents,
        )
        self.active_missions[mission_id] = oversight
        self.status = DictatorStatus.commanding

    def complete_mission(self, mission_id: str) -> None:
        self.active_missions.pop(mission_id, None)
        self.completed_missions.append(mission_id)
        if not self.active_missions:
            self.status = DictatorStatus.idle

    def log_directive(self, directive: dict) -> None:
        self.directive_log.append({
            **directive,
            "timestamp": datetime.utcnow().isoformat(),
        })
        oversight = self.active_missions.get(directive.get("mission_id", ""))
        if oversight:
            oversight.directive_count += 1


dictator_state = DictatorState()
