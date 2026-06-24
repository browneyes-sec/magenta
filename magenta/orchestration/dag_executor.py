"""DAG-based playbook executor with topological scheduling and parallel task execution."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from magenta.core.agent import agent_registry
from magenta.core.mission import mission_manager
from magenta.core.models import Mission, MissionStatus
from magenta.exceptions import MissionError

logger = logging.getLogger(__name__)


@dataclass
class DAGNode:
    """A node in the execution DAG."""
    task_id: str
    role: str
    agent_id: str | None = None
    depends_on: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed
    result: dict | None = None
    error: str | None = None
    attempts: int = 0
    max_retries: int = 2


class DAGExecutor:
    """Executes mission tasks as a DAG with parallel execution."""

    def __init__(self, max_concurrency: int = 5):
        self._running: dict[str, asyncio.Task] = {}
        self._max_concurrency = max_concurrency
        self._semaphore: asyncio.Semaphore | None = None

    def _build_dag(self, mission: Mission) -> dict[str, DAGNode]:
        """Build DAG from mission tasks/playbook stages."""
        nodes = {}

        # Use playbook stages if available, fall back to mission tasks
        stages = mission.playbook_stages if hasattr(mission, 'playbook_stages') else []

        if not stages and mission.tasks:
            # Convert linear tasks to stages
            for i, task in enumerate(mission.tasks):
                stages.append({
                    "task_id": task.get("task_id", f"task_{i}"),
                    "role": task.get("role", "triage"),
                    "depends_on": task.get("depends_on", []),
                    "params": task.get("params", {}),
                })

        if not stages:
            # Default single-stage triage
            stages = [{
                "task_id": "triage",
                "role": "triage",
                "depends_on": [],
                "params": {},
            }]

        for stage in stages:
            task_id = stage["task_id"]
            role = stage.get("role", "triage")
            depends_on = stage.get("depends_on", [])
            params = stage.get("params", {})

            # Auto-assign agent by role
            agents = agent_registry.get_by_role(role)
            agent_id = agents[0].agent_id if agents else None

            nodes[task_id] = DAGNode(
                task_id=task_id,
                role=role,
                agent_id=agent_id,
                depends_on=depends_on,
                params=params,
            )

        # Validate DAG - check for cycles
        self._validate_dag(nodes)

        return nodes

    def _validate_dag(self, nodes: dict[str, DAGNode]) -> None:
        """Validate DAG has no cycles using Kahn's algorithm."""
        in_degree = defaultdict(int)
        graph = defaultdict(list)

        for task_id, node in nodes.items():
            for dep in node.depends_on:
                if dep not in nodes:
                    logger.warning("Task %s depends on unknown task %s", task_id, dep)
                graph[dep].append(task_id)
                in_degree[task_id] += 1
            if task_id not in in_degree:
                in_degree[task_id] = 0

        # Kahn's algorithm
        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        processed = 0

        while queue:
            tid = queue.popleft()
            processed += 1
            for succ in graph[tid]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        if processed != len(nodes):
            raise MissionError("Playbook DAG contains cycles")

    def _get_ready_tasks(self, nodes: dict[str, DAGNode], completed: set[str]) -> list[str]:
        """Get tasks ready to execute (all dependencies completed)."""
        ready = []
        for task_id, node in nodes.items():
            if node.status != "pending":
                continue
            if all(dep in completed for dep in node.depends_on):
                ready.append(task_id)
        return ready

    async def execute_mission(self, mission_id: str) -> dict[str, Any]:
        """Execute a mission as a DAG."""
        mission = mission_manager.get(mission_id)
        mission_manager.update_status(mission_id, MissionStatus.executing)

        nodes = self._build_dag(mission)
        completed = set()
        results = {}
        errors = {}

        self._semaphore = asyncio.Semaphore(self._max_concurrency)

        while len(completed) < len(nodes):
            ready = self._get_ready_tasks(nodes, completed)

            if not ready:
                # Check for failed dependencies
                pending = [n for n in nodes.values() if n.status == "pending"]
                if not pending:
                    break
                failed = [n for n in nodes.values() if n.status == "failed"]
                if failed:
                    # No progress possible - remaining tasks depend on failed ones
                    for node in pending:
                        if any(dep in [f.task_id for f in failed] for dep in node.depends_on):
                            node.status = "skipped"
                            node.error = "Dependency failed"
                    continue
                await asyncio.sleep(0.1)
                continue

            # Launch ready tasks up to concurrency limit
            launch_tasks = []
            for task_id in ready[:self._max_concurrency]:
                node = nodes[task_id]
                node.status = "running"
                task = asyncio.create_task(self._execute_task(node, mission, results))
                launch_tasks.append(task)

            if launch_tasks:
                done, _ = await asyncio.wait(launch_tasks, return_when=asyncio.FIRST_COMPLETED)
                for done_task in done:
                    try:
                        await done_task
                    except Exception:
                        pass  # Handled in _execute_task

        # Collect final results
        for task_id, node in nodes.items():
            if node.status == "completed":
                results[task_id] = node.result
            elif node.status == "failed":
                errors[task_id] = node.error

        final_status = MissionStatus.completed if not errors else MissionStatus.failed
        mission_manager.update_status(mission_id, final_status)

        return {
            "mission_id": mission_id,
            "tasks_completed": len([n for n in nodes.values() if n.status == "completed"]),
            "tasks_failed": len([n for n in nodes.values() if n.status == "failed"]),
            "tasks_skipped": len([n for n in nodes.values() if n.status == "skipped"]),
            "results": results,
            "errors": errors,
        }

    async def _execute_task(
        self,
        node: DAGNode,
        mission: Mission,
        shared_results: dict[str, Any],
    ) -> None:
        """Execute a single task node with retries."""
        async with self._semaphore:
            agent = agent_registry.get_by_id(node.agent_id) if node.agent_id else None

            if not agent:
                # Find any agent with matching role
                agents = agent_registry.get_by_role(node.role)
                if agents:
                    agent = agents[0]

            if not agent:
                node.status = "failed"
                node.error = f"No agent available for role: {node.role}"
                logger.error("Task %s: %s", node.task_id, node.error)
                return

            # Build context with upstream results
            context = {
                "mission": mission,
                "upstream_results": {dep: shared_results.get(dep) for dep in node.depends_on},
                "params": node.params,
            }

            for attempt in range(node.max_retries + 1):
                node.attempts = attempt + 1
                try:
                    result = await agent.process(mission, context)
                    node.result = result
                    node.status = "completed"
                    shared_results[node.task_id] = result
                    logger.info("Task %s completed on attempt %d", node.task_id, attempt + 1)
                    return
                except Exception as e:
                    node.error = str(e)
                    logger.warning("Task %s attempt %d failed: %s", node.task_id, attempt + 1, e)
                    if attempt < node.max_retries:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff

            node.status = "failed"
            logger.error("Task %s failed after %d attempts: %s", node.task_id, node.attempts, node.error)


dag_executor = DAGExecutor()
