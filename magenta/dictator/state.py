"""Dictator global state — oversight board, mission registry, policy store."""

import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, PrivateAttr

logger = logging.getLogger(__name__)


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

    _redis_client: Any = PrivateAttr(None)

    def __init__(self, **data):
        redis_client = data.pop("redis_client", None)
        super().__init__(**data)
        self._redis_client = redis_client

    def set_policy(self, name: str, config: dict) -> None:
        self.policy_overrides[name] = config
        if self._redis_client is not None:
            try:
                asyncio.ensure_future(self._persist_policy_to_redis(name, config))
            except Exception:
                pass

    def clear_policy(self, name: str) -> None:
        self.policy_overrides.pop(name, None)
        if self._redis_client is not None:
            try:
                asyncio.ensure_future(self._delete_policy_from_redis(name))
            except Exception:
                pass

    async def persist_to_redis(self) -> None:
        if self._redis_client is None:
            return
        for name, config in self.policy_overrides.items():
            try:
                await self._redis_client.set(f"policy:{name}", json.dumps(config))
            except Exception as exc:
                logger.warning("Failed to persist policy %s to Redis: %s", name, exc)

    async def load_from_redis(self) -> None:
        if self._redis_client is None:
            return
        from magenta.dictator import load_policies_from_redis

        policies = await load_policies_from_redis(self._redis_client)
        self.policy_overrides.update(policies)
        if policies:
            logger.info("Loaded %d policy overrides from Redis", len(policies))

    async def _persist_policy_to_redis(self, name: str, config: dict) -> None:
        try:
            await self._redis_client.set(f"policy:{name}", json.dumps(config))
        except Exception as exc:
            logger.warning("Failed to persist policy %s to Redis: %s", name, exc)

    async def _delete_policy_from_redis(self, name: str) -> None:
        try:
            await self._redis_client.delete(f"policy:{name}")
        except Exception as exc:
            logger.warning("Failed to delete policy %s from Redis: %s", name, exc)

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
