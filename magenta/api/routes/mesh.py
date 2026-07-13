"""Mesh Gateway FastAPI Routes — /api/v1/mesh/* endpoints."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from magenta.api.middleware import get_tenant_id

router = APIRouter(prefix="/api/v1/mesh", tags=["mesh"])

# API key for pipeline-to-API auth (set via MAGENTA_API_KEY env var)
_API_KEY = os.environ.get("MAGENTA_API_KEY", "magenta-dev-key")


async def validate_api_key(x_api_key: str = Header(default="")) -> str:
    """Validate API key from header. Used for pipeline-to-API auth."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if x_api_key != _API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


class MeshQueryRequest(BaseModel):
    query: str
    products: list[str] | None = None
    filters: dict[str, Any] | None = None
    top_k: int = Field(default=10, ge=1, le=100)
    hybrid: bool = True
    explain: bool = False


class MeshIngestRequest(BaseModel):
    product: str
    documents: list[dict[str, Any]]
    batch_size: int = Field(default=32, ge=1, le=256)


@router.get("/health")
async def mesh_health():
    """Health check for all mesh components (Qdrant, OLLAMA, Redis)."""
    from magenta.mesh.gateway import mesh_gateway

    if not mesh_gateway._started:
        await mesh_gateway.start()

    return await mesh_gateway.health()


@router.get("/products")
async def mesh_list_products():
    """List available data products with schemas and health."""
    from magenta.mesh.gateway import mesh_gateway

    return await mesh_gateway.list_products()


@router.post("/query")
async def mesh_query(request: MeshQueryRequest):
    """Hybrid search across data products (dense + sparse + metadata via RRF)."""
    from magenta.mesh.gateway import mesh_gateway

    if not mesh_gateway._started:
        await mesh_gateway.start()

    return await mesh_gateway.query(
        query=request.query,
        products=request.products,
        filters=request.filters,
        top_k=request.top_k,
        hybrid=request.hybrid,
        explain=request.explain,
    )


@router.post("/ingest")
async def mesh_ingest(request: MeshIngestRequest):
    """Ingest documents into a data product collection."""
    from magenta.mesh.gateway import mesh_gateway

    if not mesh_gateway._started:
        await mesh_gateway.start()

    return await mesh_gateway.ingest(
        product=request.product,
        documents=request.documents,
        batch_size=request.batch_size,
    )


# ── Memory Endpoints ──────────────────────────────────────────────────────


class WriteEpisodeRequest(BaseModel):
    agent_role: str
    mission_id: str
    turn_number: int
    text: str
    correlation_id: str = ""
    metadata: dict[str, Any] | None = None


class SearchMemoryRequest(BaseModel):
    query: str
    agent_role: str = ""
    mission_id: str = ""
    tool_name: str = ""
    product: str = ""
    tags: list[str] | None = None
    top_k: int = Field(default=5, ge=1, le=50)


class WriteSemanticRequest(BaseModel):
    text: str
    product: str = "agent.memory.semantic"
    source: str = "agent"
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class WriteProceduralRequest(BaseModel):
    tool_name: str
    text: str
    parameters: dict[str, Any] | None = None
    mission_id: str = ""
    metadata: dict[str, Any] | None = None


@router.post("/memory/write-episode")
async def write_episode(
    request: WriteEpisodeRequest,
    tenant_id: str = Depends(get_tenant_id),
    _api_key: str = Depends(validate_api_key),
):
    """Write episodic memory (mission transcript, agent decision)."""
    from magenta.mesh.memory import memory_mcp

    # Inject tenant_id from auth context for multi-tenant isolation
    metadata = request.metadata or {}
    metadata["tenant_id"] = tenant_id

    return await memory_mcp.write_episode(
        agent_role=request.agent_role,
        mission_id=request.mission_id,
        turn_number=request.turn_number,
        text=request.text,
        correlation_id=request.correlation_id,
        metadata=metadata,
    )


@router.post("/memory/search-episodes")
async def search_episodes(request: SearchMemoryRequest, tenant_id: str = Depends(get_tenant_id)):
    """Search episodic memory for past agent decisions."""
    from magenta.mesh.memory import memory_mcp

    return await memory_mcp.search_episodes(
        query=request.query,
        agent_role=request.agent_role,
        mission_id=request.mission_id,
        tenant_id=tenant_id,
        top_k=request.top_k,
    )


@router.post("/memory/write-semantic")
async def write_semantic(
    request: WriteSemanticRequest,
    tenant_id: str = Depends(get_tenant_id),
    _api_key: str = Depends(validate_api_key),
):
    """Write semantic memory (playbook, runbook, policy, knowledge)."""
    from magenta.mesh.memory import memory_mcp

    metadata = request.metadata or {}
    metadata["tenant_id"] = tenant_id

    return await memory_mcp.write_semantic(
        text=request.text,
        product=request.product,
        source=request.source,
        tags=request.tags,
        metadata=metadata,
    )


@router.post("/memory/search-semantic")
async def search_semantic(request: SearchMemoryRequest, tenant_id: str = Depends(get_tenant_id)):
    """Search semantic memory for reusable knowledge."""
    from magenta.mesh.memory import memory_mcp

    return await memory_mcp.search_semantic(
        query=request.query,
        product=request.product,
        tags=request.tags,
        tenant_id=tenant_id,
        top_k=request.top_k,
    )


@router.post("/memory/write-procedure")
async def write_procedure(
    request: WriteProceduralRequest,
    tenant_id: str = Depends(get_tenant_id),
    _api_key: str = Depends(validate_api_key),
):
    """Write procedural memory (tool invocation pattern)."""
    from magenta.mesh.memory import memory_mcp

    metadata = request.metadata or {}
    metadata["tenant_id"] = tenant_id

    return await memory_mcp.write_procedure(
        tool_name=request.tool_name,
        text=request.text,
        parameters=request.parameters,
        mission_id=request.mission_id,
        metadata=metadata,
    )


@router.post("/memory/search-procedures")
async def search_procedures(request: SearchMemoryRequest, tenant_id: str = Depends(get_tenant_id)):
    """Search procedural memory for tool usage patterns."""
    from magenta.mesh.memory import memory_mcp

    return await memory_mcp.search_procedures(
        query=request.query,
        tool_name=request.tool_name,
        tenant_id=tenant_id,
        top_k=request.top_k,
    )
