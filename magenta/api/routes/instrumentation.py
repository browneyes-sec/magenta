"""API routes — integration layer versioning and artifact registry."""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _load_json(path: str) -> dict:
    try:
        full_path = Path(__file__).resolve().parent.parent.parent.parent / path
        with open(full_path) as f:
            return json.load(f)
    except Exception:
        return {}


VERSION_PATH = "soa/instrumentation/version.json"
REGISTRY_PATH = "soa/instrumentation/artifact_registry.json"


class ArtifactRegistration(BaseModel):
    name: str
    description: str = ""
    generator: str = ""
    version: str = "1.0"
    schema_: dict = {}


@router.get("/version")
async def get_integration_version():
    """Get the integration layer version manifest."""
    data = _load_json(VERSION_PATH)
    if not data:
        return {"version": "unknown", "error": "Version manifest not found"}
    return data


@router.get("/artifacts")
async def list_artifacts():
    """List all registered artifacts in the registry."""
    data = _load_json(REGISTRY_PATH)
    if not data:
        return {"artifacts": {}, "count": 0}
    return data


@router.get("/artifacts/{artifact_name}")
async def get_artifact(artifact_name: str):
    """Get details of a specific artifact type."""
    data = _load_json(REGISTRY_PATH)
    artifacts = data.get("artifacts", {})
    artifact = artifacts.get(artifact_name)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Artifact '{artifact_name}' not found")
    return {"name": artifact_name, **artifact}


@router.post("/artifacts/register")
async def register_artifact(registration: ArtifactRegistration):
    """Register a new artifact type."""
    data = _load_json(REGISTRY_PATH)
    if not data:
        data = {"version": "1.0", "artifacts": {}, "changelog": []}

    data["artifacts"][registration.name] = {
        "name": registration.name,
        "description": registration.description,
        "generator": registration.generator,
        "version": registration.version,
        "schema": registration.schema_,
    }

    try:
        full_path = Path(__file__).resolve().parent.parent.parent.parent / REGISTRY_PATH
        with open(full_path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist registry: {exc}")

    return {"status": "registered", "name": registration.name}
