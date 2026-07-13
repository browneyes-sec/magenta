"""API routes — playbooks."""

from fastapi import APIRouter, HTTPException, Query

from magenta.core.models import Playbook
from magenta.core.playbook import playbook_manager

router = APIRouter()


@router.get("/")
async def list_playbooks(tag: str | None = Query(None)):
    """List registered playbooks."""
    playbooks = playbook_manager.list(tag=tag)
    return [
        {
            "name": p.name,
            "version": p.version,
            "tags": p.tags,
            "stages": len(p.stages),
            "updated_at": p.updated_at.isoformat(),
        }
        for p in playbooks
    ]


@router.get("/{name}")
async def get_playbook(name: str, version: str | None = Query(None)):
    """Get playbook details."""
    pb = playbook_manager.get(name, version=version)
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return pb.model_dump()


@router.post("/validate")
async def validate_playbook(data: dict):
    """Validate a playbook configuration."""
    errors = []
    if "name" not in data:
        errors.append("Missing required field: name")
    return {"valid": len(errors) == 0, "errors": errors}


@router.post("/")
async def register_playbook(data: dict):
    """Register a playbook."""
    try:
        pb = Playbook(**data)
        playbook_manager.register(pb)
        return {"status": "registered", "name": pb.name, "version": pb.version}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
