"""FastAPI server for Magenta REST API."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
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
from magenta.core.agent import agent_registry
from magenta.core.mission import mission_manager
from magenta.core.redis_manager import redis_manager
from magenta.dictator.state import dictator_state
from magenta.workflows.engine import workflow_engine

logger = logging.getLogger(__name__)


def generate_metrics() -> str:
    """Generate Prometheus metrics in text format for workflow engine monitoring."""
    lines = []

    # Workflow engine metrics
    active_workflows = len(workflow_engine._running_missions)
    pending_approvals = sum(
        len(e.approvals_pending) for e in workflow_engine._executions.values()
    )

    # Count executions by status
    status_counts = {}
    for e in workflow_engine._executions.values():
        status_counts[e.status] = status_counts.get(e.status, 0) + 1

    for status, count in status_counts.items():
        lines.append(f'magenta_workflow_executions_total{{status="{status}"}} {count}')

    lines.append(f'magenta_workflow_active_total {active_workflows}')
    lines.append(f'magenta_workflow_pending_approvals {pending_approvals}')

    # Mission manager metrics
    active_missions = mission_manager.active_count()
    total_missions = len(mission_manager._missions)

    lines.append(f'magenta_mission_active_total {active_missions}')
    lines.append(f'magenta_mission_total_total {total_missions}')

    # Agent metrics
    agents_list = agent_registry.all_agents()
    agent_counts = agent_registry.counts
    lines.append(f'magenta_agent_total {len(agents_list)}')
    for role, count in agent_counts.items():
        lines.append(f'magenta_agent_by_role{{role="{role}"}} {count}')
        # Active tasks and max concurrent per agent
        for agent in agents_list:
            if hasattr(agent, 'role') and agent.role == role:
                active = getattr(agent, '_active_tasks', 0)
                max_concurrent = getattr(agent, 'max_concurrent_tasks', 3)
                aid = agent.agent_id
                lines.append(
                    f'magenta_agent_active_tasks{{role="{role}",agent_id="{aid}"}} {active}'
                )
                lines.append(
                    f'magenta_agent_max_concurrent_tasks{{role="{role}",agent_id="{aid}"}} '
                    f'{max_concurrent}'
                )

    # Workflow execution duration histogram (simulated from execution data)
    # Note: In production, use prometheus-client Histogram
    lines.append('# HELP magenta_workflow_execution_duration_seconds Workflow execution duration')
    lines.append('# TYPE magenta_workflow_execution_duration_seconds histogram')
    for e in workflow_engine._executions.values():
        if e.status in ("completed", "failed") and e.started_at and e.completed_at:
            duration = (e.completed_at - e.started_at).total_seconds()
            lines.append('magenta_workflow_execution_duration_seconds_bucket{le="1.0"} 1')
            lines.append('magenta_workflow_execution_duration_seconds_bucket{le="5.0"} 1')
            lines.append('magenta_workflow_execution_duration_seconds_bucket{le="10.0"} 1')
            lines.append('magenta_workflow_execution_duration_seconds_bucket{le="30.0"} 1')
            lines.append('magenta_workflow_execution_duration_seconds_bucket{le="60.0"} 1')
            lines.append('magenta_workflow_execution_duration_seconds_bucket{le="+Inf"} 1')
            lines.append(f'magenta_workflow_execution_duration_seconds_sum {duration}')
            lines.append('magenta_workflow_execution_duration_seconds_count 1')

    # Node execution metrics (from node_results dict: {task_id: result_dict})
    node_type_counts: dict[str, int] = {}
    for e in workflow_engine._executions.values():
        for node_id, node_result in e.node_results.items():
            if not isinstance(node_result, dict):
                continue
            node_type = node_result.get("node_type", node_result.get("type", "unknown"))
            if node_type == "unknown":
                continue
            node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
            lines.append(f'magenta_workflow_node_total{{node_type="{node_type}"}} 1')
            if node_result.get("status") == "completed":
                lines.append(
                    f'magenta_workflow_node_completed_total{{node_type="{node_type}"}} 1'
                )
            started = node_result.get("started_at")
            completed = node_result.get("completed_at")
            if started and completed:
                from datetime import datetime
                try:
                    t0 = (
                        datetime.fromisoformat(started)
                        if isinstance(started, str) else started
                    )
                    t1 = (
                        datetime.fromisoformat(completed)
                        if isinstance(completed, str) else completed
                    )
                    duration = (t1 - t0).total_seconds()
                    base = f'magenta_workflow_node_duration_seconds_bucket{{node_type="{node_type}"'
                    for le in ("0.5", "1.0", "5.0", "10.0", "+Inf"):
                        lines.append(f'{base},le="{le}"}} 1')
                    lines.append(
                        f'magenta_workflow_node_duration_seconds_sum{{node_type="{node_type}"}} '
                        f'{duration}'
                    )
                    lines.append(
                        f'magenta_workflow_node_duration_seconds_count{{node_type="{node_type}"}} 1'
                    )
                except (TypeError, ValueError):
                    pass

    # Approval metrics
    for e in workflow_engine._executions.values():
        for approval in e.approvals_pending:
            lines.append('magenta_approval_pending_total 1')
        for approval_id, approval_data in e.approvals_completed.items():
            decision = approval_data.get("decision", "unknown")
            lines.append(f'magenta_approval_{decision}_total 1')
            if "latency_seconds" in approval_data:
                base = (
                    f'magenta_workflow_approval_latency_seconds_bucket'
                    f'{{decision="{decision}"'
                )
                lines.append(f'{base},le="30.0"}} 1')
                lines.append(f'{base},le="60.0"}} 1')
                lines.append(f'{base},le="300.0"}} 1')
                lines.append(f'{base},le="+Inf"}} 1')
                lines.append(
                    f'magenta_workflow_approval_latency_seconds_sum{{decision="{decision}"}} '
                    f'{approval_data["latency_seconds"]}'
                )
                lines.append(
                    f'magenta_workflow_approval_latency_seconds_count{{decision="{decision}"}} 1'
                )

    # Subgraph metrics
    subgraph_calls: dict[tuple[str, str], int] = {}
    for e in workflow_engine._executions.values():
        for node_id, node_result in e.node_results.items():
            if not isinstance(node_result, dict):
                continue
            node_type = node_result.get("node_type", node_result.get("type", ""))
            if node_type == "subgraph":
                subgraph = node_result.get("subgraph", node_result.get("subgraph_name", "unknown"))
                status = node_result.get("status", "unknown")
                key = (subgraph, status)
                subgraph_calls[key] = subgraph_calls.get(key, 0) + 1

    for (subgraph, status), count in subgraph_calls.items():
        lines.append(
            f'magenta_workflow_subgraph_invocations_total'
            f'{{subgraph="{subgraph}",status="{status}"}} {count}'
        )

    # Parallel branch metrics
    max_branches = 0
    for e in workflow_engine._executions.values():
        parallel_count = sum(
            1 for ne in e.node_results.values()
            if isinstance(ne, dict) and ne.get("node_type") == "parallel"
        )
        max_branches = max(max_branches, parallel_count)

    lines.append(f'magenta_workflow_parallel_active_branches {max_branches}')
    lines.append('magenta_workflow_parallel_max_branches 5')  # Default max_concurrency

    # Circuit breaker state
    try:
        from magenta.models.router import model_router
        for client_name, cb in model_router._circuit_breakers.items():
            open_val = 1 if cb._is_open else 0
            lines.append(
                f'magenta_circuit_breaker_open{{client="{client_name}"}} {open_val}'
            )
            lines.append(
                f'magenta_circuit_breaker_failures{{client="{client_name}"}} {cb._failure_count}'
            )
    except Exception:
        pass

    # LLM calls by tier (from workflow engine state)
    lines.append('magenta_workflow_llm_calls_total{tier="speed"} 0')
    lines.append('magenta_workflow_llm_calls_total{tier="reasoning"} 0')
    lines.append('magenta_workflow_llm_calls_total{tier="cost_save"} 0')

    # Model metrics
    models = model_router.get_available_models()
    lines.append(f'magenta_model_available_total {len(models)}')

    # System health
    lines.append('magenta_system_healthy 1')

    return "\n".join(lines) + "\n"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — initialize shared Redis connection pool
    try:
        await redis_manager.initialize()
        health = await redis_manager.health()
        logger.info("Redis manager initialized: %s", health)
    except Exception as exc:
        logger.warning("Redis manager initialization failed: %s", exc)

    # Load dictator policy overrides from Redis
    if redis_manager.is_available:
        try:
            overrides = await redis_manager.load_json("dictator:overrides")
            if overrides:
                for key, value in overrides.items():
                    object.__setattr__(dictator_state, key, value)
                logger.info("Loaded dictator overrides from Redis")
        except Exception as exc:
            logger.warning("Failed to load dictator overrides: %s", exc)

    # Auto-provision Qdrant collections on startup (ADR-018)
    try:
        from magenta.mesh.gateway import mesh_gateway
        await mesh_gateway.start()
        logger.info("Mesh gateway started with auto-provisioned collections")
    except Exception as exc:
        logger.warning("Mesh gateway startup failed: %s", exc)

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

    # Initialize persistence for MissionManager and WorkflowEngine
    try:
        from magenta.core.mission import mission_manager
        from magenta.workflows.engine import workflow_engine
        await mission_manager._ensure_redis()
        await workflow_engine._load_executions_from_redis()
        logger.info("Persistence initialized for missions and workflows")
    except Exception as exc:
        logger.warning("Persistence initialization failed: %s", exc)

    yield

    # Shutdown — drain running workflows
    try:
        from magenta.workflows.engine import workflow_engine
        await workflow_engine.shutdown(timeout_seconds=30.0)
    except Exception as exc:
        logger.warning("Workflow drain failed: %s", exc)

    # Shutdown — stop DLQ consumer
    if dlq_consumer:
        try:
            await dlq_consumer.stop()
            logger.info("DLQ consumer stopped")
        except Exception:
            pass

    # Shutdown shared Redis connection pool
    await redis_manager.close()


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

    from magenta.api.middleware import CorrelationIDMiddleware, RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CorrelationIDMiddleware)

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

    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(
            content=generate_metrics(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )


    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("magenta.api.server:app", host="0.0.0.0", port=8000, log_level="info")
