"""Microsoft Sentinel webhook handler."""

from typing import Any
from datetime import datetime

from magenta.core.mission import mission_manager
from magenta.core.models import MissionStatus
from magenta.core.swarm import swarm_manager


async def handle_incident(payload: dict) -> dict:
    """Handle a Sentinel incident webhook."""
    incident = payload.get("Incident", {})
    alert_id = incident.get("IncidentNumber", incident.get("SystemAlertId", "unknown"))

    mission = mission_manager.create(
        alert_id=alert_id,
        source_system="sentinel",
        description=incident.get("Title", f"Sentinel incident {alert_id}"),
    )

    if incident.get("Severity") == "High":
        mission.severity = 4
    elif incident.get("Severity") == "Critical":
        mission.severity = 5
    elif incident.get("Severity") == "Medium":
        mission.severity = 3
    else:
        mission.severity = 2

    mission.artifact_bundle["raw_incident"] = incident
    mission_manager.update_status(mission.mission_id, MissionStatus.assigned)

    return {
        "mission_id": mission.mission_id,
        "alert_id": alert_id,
        "status": "mission_created",
    }
