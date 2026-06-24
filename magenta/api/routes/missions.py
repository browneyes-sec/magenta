"""API routes — missions."""


from fastapi import APIRouter, HTTPException, Query

from magenta.core.mission import mission_manager
from magenta.orchestration.engine import orchestration_engine

router = APIRouter()


@router.get("/")
async def list_missions(
    status: str | None = Query(None),
    limit: int = Query(50),
):
    """List missions."""
    missions = mission_manager.list(status=status)[:limit]
    return [
        {
            "mission_id": m.mission_id,
            "status": m.status.value,
            "alert_id": m.alert_id,
            "severity": m.severity.value,
            "tasks": len(m.tasks),
            "team_size": len(m.team),
            "created_at": m.created_at.isoformat(),
        }
        for m in missions
    ]


@router.get("/{mission_id}")
async def get_mission(mission_id: str):
    """Get mission details."""
    try:
        mission = mission_manager.get(mission_id)
        return mission.model_dump()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/")
async def create_mission(
    alert_id: str = Query(...),
    source: str = Query("sentinel"),
    description: str = Query(""),
):
    """Create a new mission."""
    mission = mission_manager.create(
        alert_id=alert_id,
        source_system=source,
        description=description,
    )
    return mission.model_dump()


@router.post("/{mission_id}/start")
async def start_mission(mission_id: str):
    """Start mission execution."""
    try:
        await orchestration_engine.start_mission(mission_id)
        return {"status": "started", "mission_id": mission_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{mission_id}/stop")
async def stop_mission(mission_id: str):
    """Stop mission execution."""
    try:
        await orchestration_engine.stop_mission(mission_id)
        return {"status": "stopped", "mission_id": mission_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{mission_id}/logs")
async def get_mission_logs(
    mission_id: str,
    tail: int = Query(100),
):
    """Get mission logs."""
    try:
        logs = await orchestration_engine.get_mission_logs(mission_id, tail=tail)
        return {"mission_id": mission_id, "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
