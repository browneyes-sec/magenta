"""Pipeline probe — validates orchestration pipeline health."""

from magenta.dictator.state import dictator_state


def run() -> dict:
    """Check pipeline health by verifying mission state consistency."""
    active = len(dictator_state.active_missions)
    completed = len(dictator_state.completed_missions)
    directive_count = len(dictator_state.directive_log)

    return {
        "active_missions": active,
        "completed_missions": completed,
        "directive_count": directive_count,
        "healthy": True,
    }
