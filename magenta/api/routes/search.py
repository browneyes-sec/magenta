"""API routes — search across registries."""

from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()


@router.get("/")
async def search(
    q: str = Query(..., description="Search query"),
    source: Optional[str] = Query(None, description="Filter by source (elastic, sentinel, lake)"),
    limit: int = Query(50),
):
    """Search across all registries.

    Queries Elasticsearch hot index, Sentinel custom tables,
    and Data Lake cold storage.
    """
    # Stub — real implementation queries ES + Sentinel + Lake
    return {
        "query": q,
        "source": source or "all",
        "total": 0,
        "results": [],
        "took_ms": 0,
    }


@router.get("/activity")
async def search_activity(
    correlation_id: Optional[str] = Query(None),
    alert_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """Search automation.activity events."""
    return {
        "filters": {
            "correlation_id": correlation_id,
            "alert_id": alert_id,
            "action": action,
            "status": status,
        },
        "total": 0,
        "results": [],
    }
