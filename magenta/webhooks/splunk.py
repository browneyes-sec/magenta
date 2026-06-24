"""Splunk webhook handler."""

from magenta.core.mission import mission_manager


async def handle_alert(payload: dict) -> dict:
    """Handle a Splunk alert webhook."""
    search_name = payload.get("search_name", "unknown")
    results = payload.get("result", {})

    alert_id = results.get("id", results.get("sid", f"splunk-{search_name}"))

    mission = mission_manager.create(
        alert_id=alert_id,
        source_system="splunk",
        description=f"Splunk alert: {search_name}",
    )

    severity = results.get("severity", "medium")
    severity_map = {"critical": 5, "high": 4, "medium": 3, "low": 2}
    mission.severity = severity_map.get(severity.lower(), 3)

    mission.artifact_bundle["search_name"] = search_name
    mission.artifact_bundle["raw_results"] = results

    return {
        "mission_id": mission.mission_id,
        "alert_id": alert_id,
        "search_name": search_name,
        "status": "mission_created",
    }
