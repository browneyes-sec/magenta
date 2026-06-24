import json
import logging
from typing import Any

from magenta.dictator.directives import Directive, DirectivePriority, DirectiveType, issue_directive
from magenta.dictator.policies import OrchestrationPolicy, PolicyEngine
from magenta.dictator.state import DictatorState, MissionOversight, dictator_state
from magenta.dictator.telemetry import (
    emit_directive_span,
    generate_directive_timeline_artifact,
    write_directive_to_elastic,
)

logger = logging.getLogger(__name__)


async def load_policies_from_redis(redis_client) -> dict[str, Any]:
    """Read all keys matching policy:* from Redis and return as dict of name -> config.

    Best-effort: returns empty dict on any failure.
    """
    try:
        keys = await redis_client.keys("policy:*")
        if not keys:
            return {}
        values = await redis_client.mget(*keys)
        policies: dict[str, Any] = {}
        for key, value in zip(keys, values):
            if value is not None:
                key_str = key if isinstance(key, str) else key.decode("utf-8")
                name = key_str.split(":", 1)[1]
                policies[name] = json.loads(value)
        return policies
    except Exception as exc:
        logger.warning("Failed to load policies from Redis: %s", exc)
        return {}


__all__ = [
    "dictator_state",
    "DictatorState",
    "MissionOversight",
    "Directive",
    "DirectiveType",
    "DirectivePriority",
    "issue_directive",
    "PolicyEngine",
    "OrchestrationPolicy",
    "emit_directive_span",
    "write_directive_to_elastic",
    "generate_directive_timeline_artifact",
    "load_policies_from_redis",
]
