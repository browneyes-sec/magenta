"""Generic webhook handler for custom integrations."""

from typing import Any

from magenta.core.mission import mission_manager
from magenta.core.models import MissionStatus


async def handle_webhook(payload: dict) -> dict:
    """Handle a generic JSON webhook payload."""
    alert_id = payload.get("alert_id", payload.get("id", f"generic-{hash(str(payload)) % 100000}"))
    source = payload.get("source", payload.get("system", "generic"))

    mission = mission_manager.create(
        alert_id=str(alert_id),
        source_system="sentinel",
        description=payload.get("description", payload.get("message", f"Generic alert {alert_id}")),
    )

    mission.artifact_bundle["raw_payload"] = payload
    mission_manager.update_status(mission.mission_id, MissionStatus.assigned)

    return {
        "mission_id": mission.mission_id,
        "alert_id": str(alert_id),
        "source": source,
        "status": "mission_created",
    }
