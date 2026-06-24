"""API routes — search across registries."""

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/")
async def search(
    q: str = Query(..., description="Search query"),
    source: str | None = Query(None, description="Filter by source (elastic, sentinel, lake)"),
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
    correlation_id: str | None = Query(None),
    alert_id: str | None = Query(None),
    action: str | None = Query(None),
    status: str | None = Query(None),
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
