"""FastAPI server for Magenta REST API."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from magenta import __about__
from magenta.api.routes import (
    agents,
    approvals,
    dictator,
    health,
    ingest,
    instrumentation,
    mcp,
    mesh,
    missions,
    monitoring,
    playbooks,
    search,
    workflows,
)
from magenta.config import settings
from magenta.dictator.state import dictator_state

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — connect to Redis for policy persistence
    redis_url = os.environ.get("REDIS_URL", "redis://magenta-redis:6379/0")
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        object.__setattr__(dictator_state, "_redis_client", redis_client)
        await dictator_state.load_from_redis()
        logger.info("Connected to Redis at %s and loaded policy overrides", redis_url)
    except Exception as exc:
        logger.warning(
            "Redis unavailable at %s, continuing without persistence: %s",
            redis_url, exc,
        )

    # Initialize LangGraph subgraphs for workflow engine
    try:
        from magenta.workflows.langgraph.engine import initialize_subgraphs
        initialize_subgraphs()
        logger.info("LangGraph subgraphs initialized")
    except Exception as exc:
        logger.warning("LangGraph subgraph initialization failed: %s", exc)

    # Start DLQ consumer for dead-letter topics
    dlq_consumer = None
    try:
        from magenta.integration.dlq_consumer import DLQConsumer
        from magenta.integration.eventhub import EventHubClient

        eh_client = EventHubClient(
            namespace=settings.eventhub.namespace,
            connection_string=settings.eventhub.connection_string or "",
        )
        dlq_consumer = DLQConsumer(eh_client)
        await dlq_consumer.start()
        logger.info("DLQ consumer started for dead-letter topics")
    except Exception as exc:
        logger.warning("DLQ consumer not started: %s", exc)

    yield

    # Shutdown — stop DLQ consumer
    if dlq_consumer:
        try:
            await dlq_consumer.stop()
            logger.info("DLQ consumer stopped")
        except Exception:
            pass

    # Shutdown Redis
    if dictator_state._redis_client is not None:
        await dictator_state._redis_client.close()
        logger.info("Redis connection closed")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Magenta ASOAR API",
        description="Agentic System Orchestration Automation and Response",
        version=__about__.__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.origins,
        allow_credentials=settings.cors.allow_credentials,
        allow_methods=settings.cors.allow_methods,
        allow_headers=settings.cors.allow_headers,
    )

    if settings.security_headers.enabled:
        from magenta.api.middleware.security import SecurityHeadersMiddleware
        app.add_middleware(SecurityHeadersMiddleware)

    if settings.entra_jwt.enabled:
        from magenta.api.middleware.auth import EntraJWTAuthMiddleware
        app.add_middleware(EntraJWTAuthMiddleware)

    app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
    app.include_router(missions.router, prefix="/api/v1/missions", tags=["Missions"])
    app.include_router(playbooks.router, prefix="/api/v1/playbooks", tags=["Playbooks"])
    app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
    app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
    app.include_router(dictator.router, prefix="/api/v1/dictator", tags=["Dictator"])
    app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["Approvals"])
    app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["Monitoring"])
    app.include_router(
        instrumentation.router,
        prefix="/api/v1/instrumentation",
        tags=["Instrumentation"],
    )
    app.include_router(ingest.router, prefix="/ingest", tags=["Ingest"])
    app.include_router(mesh.router, prefix="/api/v1/mesh", tags=["Data Mesh"])
    app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["Workflows"])
    app.include_router(mcp.router, tags=["MCP"])

    @app.get("/")
    async def root():
        return {
            "service": "Magenta ASOAR",
            "version": __about__.__version__,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("magenta.api.server:app", host="0.0.0.0", port=8000, log_level="info")
