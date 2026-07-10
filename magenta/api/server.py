"""FastAPI server for Magenta REST API."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from magenta.api.routes import agents, missions, playbooks, health, search, dictator, approvals
from magenta import __about__


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    pass


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
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
    app.include_router(missions.router, prefix="/api/v1/missions", tags=["Missions"])
    app.include_router(playbooks.router, prefix="/api/v1/playbooks", tags=["Playbooks"])
    app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
    app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
    app.include_router(dictator.router, prefix="/api/v1/dictator", tags=["Dictator"])
    app.include_router(approvals.router, prefix="/api/v1", tags=["Approvals"])

    @app.get("/")
    async def root():
        return {
            "service": "Magenta ASOAR",
            "version": __about__.__version__,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app
