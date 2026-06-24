"""Workflow Engine - Executes compiled workflows with agentic nodes, approvals, and publishing."""

from __future__ import annotations

import ast
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from magenta.core.agent import agent_registry
from magenta.core.mission import mission_manager
from magenta.core.models import Mission, MissionStatus
from magenta.core.redis_manager import redis_manager
from magenta.logging import get_structured_logger
from magenta.orchestration.dag_executor import DAGNode, dag_executor
from magenta.workflows.compiler import workflow_compiler

_logger = get_structured_logger(__name__)


def _safe_eval(expression: str, context: dict[str, Any]) -> bool:
    """Safely evaluate a boolean expression without arbitrary code execution.

    Supports: comparisons (==, !=, <, >, <=, >=), boolean operators (and, or, not),
    attribute access, subscript access, string/number/boolean literals.

    Raises ValueError for unsupported AST node types.
    """
    tree = ast.parse(expression, mode="eval")

    def _eval_node(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in context:
                raise ValueError(f"Unknown variable: {node.id}")
            return context[node.id]
        if isinstance(node, ast.Attribute):
            obj = _eval_node(node.value)
            return getattr(obj, node.attr)
        if isinstance(node, ast.Subscript):
            obj = _eval_node(node.value)
            key = _eval_node(node.slice)
            return obj[key]
        if isinstance(node, ast.Compare):
            left = _eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = _eval_node(comparator)
                if not _eval_cmp(op, left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(_eval_node(v) for v in node.values)
            if isinstance(node.op, ast.Or):
                return any(_eval_node(v) for v in node.values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _eval_node(node.operand)
        if isinstance(node, ast.Call):
            raise ValueError("Function calls not allowed in conditions")
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    def _eval_cmp(op: ast.cmpop, left: Any, right: Any) -> bool:
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.LtE):
            return left <= right
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.GtE):
            return left >= right
        if isinstance(op, ast.In):
            return left in right
        if isinstance(op, ast.NotIn):
            return left not in right
        raise ValueError(f"Unsupported operator: {type(op).__name__}")

    return bool(_eval_node(tree))


@dataclass
class WorkflowExecution:
    mission_id: str
    playbook_name: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    status: str = "running"
    node_results: dict = field(default_factory=dict)
    node_errors: dict = field(default_factory=dict)
    approvals_pending: dict = field(default_factory=dict)
    current_node: str | None = None
    correlation_id: str = ""

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "playbook_name": self.playbook_name,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "node_results": self.node_results,
            "node_errors": self.node_errors,
            "approvals_pending": self.approvals_pending,
            "current_node": self.current_node,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> WorkflowExecution:
        started_at = datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
        completed_at = (
            datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
        )
        return cls(
            mission_id=data["mission_id"],
            playbook_name=data["playbook_name"],
            started_at=started_at or datetime.utcnow(),
            completed_at=completed_at,
            status=data.get("status", "running"),
            node_results=data.get("node_results", {}),
            node_errors=data.get("node_errors", {}),
            approvals_pending=data.get("approvals_pending", {}),
            current_node=data.get("current_node"),
            correlation_id=data.get("correlation_id", ""),
        )


class WorkflowEngine:
    """High-level workflow engine that orchestrates playbook execution."""

    _MAX_COMPLETED_EXECUTIONS = 500

    def __init__(self):
        self._executions: dict[str, WorkflowExecution] = {}
        self._approval_callbacks: dict[str, asyncio.Future] = {}
        self._approval_lock = asyncio.Lock()
        self._running_missions: set[str] = set()
        self._running_lock = asyncio.Lock()

    async def _save_execution(self, execution: WorkflowExecution) -> None:
        """Persist execution state to Redis via shared manager."""
        await redis_manager.save_json(
            f"workflow_execution:{execution.mission_id}",
            execution.to_dict(),
        )

    async def _remove_execution(self, mission_id: str) -> None:
        """Remove execution from Redis via shared manager."""
        await redis_manager.remove(f"workflow_execution:{mission_id}")

    async def _load_executions_from_redis(self) -> None:
        """Load active executions from Redis via shared manager."""
        keys = await redis_manager.keys("workflow_execution:*")
        for key in keys:
            data = await redis_manager.load_json(key)
            if data and data.get("status") in ("running", "waiting_approval"):
                execution = WorkflowExecution.from_dict(data)
                self._executions[execution.mission_id] = execution
        _logger.info("Loaded %d active workflow executions from Redis", len(keys))

    async def execute_playbook(
        self,
        playbook: str | Path,
        alert_id: str,
        source_system: str,
        description: str = "",
        parameters: dict | None = None,
    ) -> str:
        """Execute a playbook from file, returning mission_id."""
        from uuid import uuid4

        correlation_id = f"wf-{uuid4().hex[:12]}"
        pb = workflow_compiler.load_playbook(playbook)

        legacy_pb = pb.to_legacy() if isinstance(pb, type(pb)) and hasattr(pb, "to_legacy") else pb

        mission = mission_manager.create(
            alert_id=alert_id,
            source_system=source_system,
            playbook=legacy_pb,
            description=description,
        )

        if parameters:
            mission.artifact_bundle.update({"workflow_parameters": parameters})

        execution = WorkflowExecution(
            mission_id=mission.mission_id,
            playbook_name=legacy_pb.name,
            correlation_id=correlation_id,
        )
        self._executions[mission.mission_id] = execution
        self._evict_old_executions()
        await self._save_execution(execution)

        _logger.info(
            "Workflow execution started",
            extra={
                "mission_id": mission.mission_id,
                "correlation_id": correlation_id,
                "playbook": legacy_pb.name,
                "alert_id": alert_id,
                "source_system": source_system,
                "action": "execute_playbook",
            },
        )

        asyncio.create_task(self._run_workflow(mission.mission_id, pb))

        return mission.mission_id

    def _evict_old_executions(self) -> None:
        """Evict oldest completed executions when over capacity."""
        if len(self._executions) <= self._MAX_COMPLETED_EXECUTIONS:
            return
        completed = [
            mid for mid, ex in self._executions.items() if ex.status in ("completed", "failed")
        ]
        completed.sort(key=lambda mid: self._executions[mid].completed_at or datetime.min)
        to_remove = completed[: len(completed) - self._MAX_COMPLETED_EXECUTIONS + 50]
        for mid in to_remove:
            self._executions.pop(mid, None)

    async def _run_workflow(self, mission_id: str, playbook: Any) -> None:
        async with self._running_lock:
            if mission_id in self._running_missions:
                _logger.warning(
                    "Mission already running, skipping duplicate",
                    extra={
                        "mission_id": mission_id,
                        "correlation_id": self._executions.get(
                            mission_id, WorkflowExecution("", "")
                        ).correlation_id,
                    },
                )
                return
            self._running_missions.add(mission_id)

        execution = self._executions[mission_id]
        cid = execution.correlation_id

        try:
            mission_manager.update_status(mission_id, MissionStatus.executing)
            _logger.info(
                "Workflow DAG compilation started",
                extra={
                    "mission_id": mission_id,
                    "correlation_id": cid,
                    "playbook": execution.playbook_name,
                    "action": "compile",
                },
            )

            nodes = workflow_compiler.compile(playbook)

            result = await self._execute_dag_with_approvals(mission_id, nodes)

            execution.completed_at = datetime.utcnow()
            execution.status = "completed" if not result.get("errors") else "failed"
            execution.node_results = result.get("results", {})
            execution.node_errors = result.get("errors", {})

            has_errors = bool(result.get("errors"))
            final_status = MissionStatus.completed if not has_errors else MissionStatus.failed
            mission_manager.update_status(mission_id, final_status)

            _logger.info(
                "Workflow execution completed",
                extra={
                    "mission_id": mission_id,
                    "correlation_id": cid,
                    "status": execution.status,
                    "tasks_completed": result.get("tasks_completed", 0),
                    "tasks_failed": result.get("tasks_failed", 0),
                    "tasks_skipped": result.get("tasks_skipped", 0),
                    "action": "workflow_complete",
                },
            )

        except Exception as e:
            _logger.error(
                f"Workflow execution failed: {e}",
                extra={
                    "mission_id": mission_id,
                    "correlation_id": cid,
                    "error": str(e),
                    "action": "workflow_error",
                },
            )
            execution.status = "failed"
            execution.completed_at = datetime.utcnow()
            execution.node_errors["workflow"] = str(e)
            mission_manager.update_status(mission_id, MissionStatus.failed)
        finally:
            await self._save_execution(execution)
            async with self._running_lock:
                self._running_missions.discard(mission_id)

    async def _execute_dag_with_approvals(
        self,
        mission_id: str,
        nodes: dict[str, DAGNode],
    ) -> dict[str, Any]:
        """Execute DAG with support for approval gates."""
        execution = self._executions[mission_id]
        mission = mission_manager.get(mission_id)

        completed = set()
        results = {}
        errors = {}
        skipped = set()

        semaphore = asyncio.Semaphore(dag_executor._max_concurrency)

        while len(completed) + len(skipped) < len(nodes):
            ready = self._get_ready_tasks(nodes, completed, skipped)

            if not ready:
                pending = [n for n in nodes.values() if n.status == "pending"]
                if not pending:
                    break

                failed_nodes = [n for n in nodes.values() if n.status == "failed"]
                if failed_nodes:
                    for node in pending:
                        if any(dep in [f.task_id for f in failed_nodes] for dep in node.depends_on):
                            node.status = "skipped"
                            node.error = "Dependency failed"
                            skipped.add(node.task_id)
                    continue

                approval_nodes = [n for n in nodes.values() if n.status == "waiting_approval"]
                if approval_nodes:
                    await asyncio.sleep(1)
                    continue

                await asyncio.sleep(0.1)
                continue

            launch_tasks = []
            for task_id in ready[: dag_executor._max_concurrency]:
                node = nodes[task_id]
                node.status = "running"
                execution.current_node = task_id
                task = asyncio.create_task(
                    self._execute_node_with_approval(node, mission, results, semaphore)
                )
                launch_tasks.append(task)

            if launch_tasks:
                done, _ = await asyncio.wait(launch_tasks, return_when=asyncio.FIRST_COMPLETED)
                for done_task in done:
                    try:
                        await done_task
                    except Exception:
                        pass

        for task_id, node in nodes.items():
            if node.status == "completed":
                results[task_id] = node.result
                completed.add(task_id)
            elif node.status == "failed":
                errors[task_id] = node.error
            elif node.status == "skipped":
                skipped.add(task_id)

        return {
            "tasks_completed": len(completed),
            "tasks_failed": len(errors),
            "tasks_skipped": len(skipped),
            "results": results,
            "errors": errors,
        }

    def _get_ready_tasks(
        self,
        nodes: dict[str, DAGNode],
        completed: set[str],
        skipped: set[str],
    ) -> list[str]:
        ready = []
        for task_id, node in nodes.items():
            if node.status != "pending":
                continue
            deps_met = all(dep in completed or dep in skipped for dep in node.depends_on)
            if deps_met:
                ready.append(task_id)
        return ready

    async def _execute_node_with_approval(
        self,
        node: DAGNode,
        mission: Mission,
        shared_results: dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> None:
        async with semaphore:
            node_type = node.params.get("node_type", "agentic")

            if node_type == "approval":
                await self._handle_approval_node(node, mission, shared_results)
            elif node_type == "decision":
                await self._handle_decision_node(node, mission, shared_results)
            elif node_type == "parallel":
                await self._handle_parallel_node(node, mission, shared_results)
            elif node_type == "subgraph":
                await self._handle_subgraph_node(node, mission, shared_results)
            else:
                await self._execute_standard_node(node, mission, shared_results)

    async def _handle_approval_node(
        self,
        node: DAGNode,
        mission: Mission,
        shared_results: dict[str, Any],
    ) -> None:
        """Handle human approval gate."""
        from magenta.api.routes.approvals import create_approval_request

        approval_config = node.params
        risk_score = approval_config.get("risk_score", 50)

        approval_id = await create_approval_request(
            mission_id=mission.mission_id,
            action=approval_config.get("action", "unknown"),
            target=approval_config.get("target", {}),
            risk_score=risk_score,
            reasoning=approval_config.get("reasoning", "Workflow approval required"),
            expires_minutes=approval_config.get("timeout_minutes", 30),
        )

        node.status = "waiting_approval"
        node.result = {"approval_id": approval_id, "status": "pending"}

        execution = self._executions[mission.mission_id]
        execution.approvals_pending[approval_id] = node.task_id
        await self._save_execution(execution)

        future = asyncio.get_running_loop().create_future()
        self._approval_callbacks[approval_id] = future

        try:
            timeout = approval_config.get("timeout_minutes", 30) * 60
            decision = await asyncio.wait_for(future, timeout=timeout)
            node.result = {"approval_id": approval_id, "status": decision}
            if decision == "approved":
                node.status = "completed"
            else:
                node.status = "failed"
                node.error = f"Approval {decision}"
        except TimeoutError:
            node.status = "failed"
            node.error = "Approval timeout"
        finally:
            execution.approvals_pending.pop(approval_id, None)
            self._approval_callbacks.pop(approval_id, None)
            await self._save_execution(execution)

    async def _handle_decision_node(
        self,
        node: DAGNode,
        mission: Mission,
        shared_results: dict[str, Any],
    ) -> None:
        """Evaluate decision condition and route accordingly."""
        condition = node.params.get("condition", "")

        if not condition:
            node.status = "failed"
            node.error = "No condition specified for decision node"
            return

        try:
            context = {
                "mission": mission,
                "upstream_results": {dep: shared_results.get(dep) for dep in node.depends_on},
                "params": mission.artifact_bundle.get("workflow_parameters", {}),
            }

            result = _safe_eval(condition, context)

            node.result = {"condition": condition, "result": bool(result)}
            node.status = "completed"

        except Exception as e:
            node.status = "failed"
            node.error = f"Decision evaluation failed: {e}"

    async def _handle_parallel_node(
        self,
        node: DAGNode,
        mission: Mission,
        shared_results: dict[str, Any],
    ) -> None:
        """Execute parallel branches (fan-out/fan-in)."""
        branches = node.params.get("branches", [])

        if not branches:
            node.status = "completed"
            node.result = {"branches": []}
            return

        branch_results = []
        for branch in branches:
            branch_node = DAGNode(
                task_id=f"{node.task_id}_{branch['id']}",
                role=branch.get("role", "triage"),
                depends_on=[],
                params=branch.get("params", {}),
            )
            await self._execute_standard_node(branch_node, mission, shared_results)
            branch_results.append(
                {
                    "id": branch["id"],
                    "result": branch_node.result,
                    "status": branch_node.status,
                }
            )

        node.result = {"branches": branch_results}
        all_ok = all(b["status"] == "completed" for b in branch_results)
        node.status = "completed" if all_ok else "failed"

    async def _handle_subgraph_node(
        self,
        node: DAGNode,
        mission: Mission,
        shared_results: dict[str, Any],
    ) -> None:
        """Execute a LangGraph subgraph."""
        subgraph_name = node.params.get("subgraph_name")

        if not subgraph_name:
            node.status = "failed"
            node.error = "No subgraph specified"
            return

        from magenta.workflows.langgraph.engine import get_subgraph

        try:
            subgraph = get_subgraph(subgraph_name)
            if not subgraph:
                node.status = "failed"
                node.error = f"Subgraph not found: {subgraph_name}"
                return

            state = {
                "mission_id": mission.mission_id,
                "alert": {
                    "id": mission.alert_id,
                    "source": mission.source_system.value,
                    "description": mission.description,
                },
                "context": {
                    "upstream_results": {dep: shared_results.get(dep) for dep in node.depends_on},
                    "params": mission.artifact_bundle.get("workflow_parameters", {}),
                },
                "upstream_results": {dep: shared_results.get(dep) for dep in node.depends_on},
                "agent_outputs": [],
                "approvals": {},
                "artifacts": {},
            }

            config = {"configurable": {"thread_id": f"{mission.mission_id}_{node.task_id}"}}
            result = await subgraph.ainvoke(state, config=config)

            node.result = result
            node.status = "completed"
            shared_results[node.task_id] = result

        except Exception as e:
            _logger.exception(f"Subgraph {subgraph_name} execution failed")
            node.status = "failed"
            node.error = str(e)

    async def _execute_standard_node(
        self,
        node: DAGNode,
        mission: Mission,
        shared_results: dict[str, Any],
    ) -> None:
        """Execute a standard agent node via DAG executor."""
        agent = agent_registry.get_by_id(node.agent_id) if node.agent_id else None

        if not agent:
            available = agent_registry.get_available_for_role(node.role)
            if available:
                agent = available[0]

        if not agent:
            node.status = "failed"
            node.error = f"No agent available for role: {node.role}"
            return

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
                return
            except Exception as e:
                node.error = str(e)
                if attempt < node.max_retries:
                    await asyncio.sleep(2**attempt)

        node.status = "failed"

    async def respond_to_approval(self, approval_id: str, decision: str) -> bool:
        """Callback for approval response."""
        async with self._approval_lock:
            future = self._approval_callbacks.get(approval_id)
            if future and not future.done():
                future.set_result(decision)
                return True
            return False

    def get_execution_status(self, mission_id: str) -> WorkflowExecution | None:
        return self._executions.get(mission_id)

    async def shutdown(self, timeout_seconds: float = 30.0) -> None:
        """Gracefully drain running workflows before shutdown."""
        if not self._running_missions:
            return
        _logger.info(
            "Draining %d running workflow(s) with timeout %.1fs",
            len(self._running_missions),
            timeout_seconds,
        )
        deadline = time.monotonic() + timeout_seconds
        while self._running_missions and time.monotonic() < deadline:
            await asyncio.sleep(0.5)
        if self._running_missions:
            _logger.warning(
                "Timed out waiting for %d workflow(s): %s",
                len(self._running_missions),
                list(self._running_missions),
            )
        else:
            _logger.info("All running workflows drained successfully")


workflow_engine = WorkflowEngine()
