"""API dependency injection."""


from magenta.config import settings
from magenta.core.agent import agent_registry
from magenta.core.mission import mission_manager
from magenta.core.playbook import playbook_manager
from magenta.models.router import model_router
from magenta.orchestration.engine import orchestration_engine


def get_settings() -> settings.__class__:
    return settings


def get_mission_manager():
    return mission_manager


def get_playbook_manager():
    return playbook_manager


def get_agent_registry():
    return agent_registry


def get_model_router():
    return model_router


def get_orchestration_engine():
    return orchestration_engine
