"""API routes — monitoring and telemetry."""

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/probes")
async def run_probes():
    """Run magnet probes and return structured results."""
    import asyncio
    import importlib

    probes = ["dictator_probe"]
    results = {}
    for name in probes:
        try:
            mod = importlib.import_module(f"magnet.probes.{name}")
            if asyncio.iscoroutinefunction(mod.run):
                results[name] = await mod.run()
            else:
                results[name] = mod.run()
        except Exception as exc:
            results[name] = {"status": "error", "error": str(exc)}
    return {"probes": results, "count": len(results)}


@router.get("/directives/rate")
async def directive_rate(minutes: int = Query(60, ge=1, le=1440)):
    """Get directive issuance rate over the given window."""
    from datetime import datetime, timedelta

    from magenta.dictator.state import dictator_state

    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    recent = [
        d for d in dictator_state.directive_log if d.get("timestamp", "") >= cutoff.isoformat()
    ]
    return {
        "window_minutes": minutes,
        "total": len(recent),
        "rate_per_minute": round(len(recent) / max(minutes, 1), 2),
        "directives": recent[-50:],
    }


@router.get("/approvals/pending/count")
async def pending_approvals_count():
    """Get the number of pending approvals."""
    from magenta.response.executor import approval_gate

    pending = await approval_gate.list_pending()
    return {"pending_count": len(pending)}


@router.get("/telemetry/directives")
async def telemetry_directives(limit: int = Query(50, ge=1, le=500)):
    """Get directive telemetry from Elasticsearch (best-effort)."""
    try:
        from magenta.data.elastic.client import elastic_client

        results = await elastic_client.search(
            "directives",
            {
                "size": limit,
                "sort": [{"logged_at": {"order": "desc"}}],
            },
        )
        return {"source": "elasticsearch", "count": len(results), "directives": results}
    except Exception:
        from magenta.dictator.state import dictator_state

        directives = dictator_state.directive_log[-limit:]
        return {"source": "in-memory", "count": len(directives), "directives": directives}
