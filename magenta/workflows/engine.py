"""Workflow Engine - Executes compiled workflows with agentic nodes, approvals, and publishing."""

from __future__ import annotations
from typing import Any, Optional
import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass, field

from magenta.core.models import Mission, MissionStatus, AgentConfig
from magenta.core.mission import mission_manager
from magenta.core.agent import agent_registry
from magenta.orchestration.dag_executor import dag_executor, DAGNode
from magenta.workflows.compiler import workflow_compiler
from magenta.exceptions import MissionError, PlaybookError

logger = logging.getLogger(__name__)


@dataclass
class WorkflowExecution:
    mission_id: str
    playbook_name: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str = "running"
    node_results: dict = field(default_factory=dict)
    node_errors: dict = field(default_factory=dict)
    approvals_pending: dict = field(default_factory=dict)
    current_node: Optional[str] = None


class WorkflowEngine:
    """High-level workflow engine that orchestrates playbook execution."""
    
    def __init__(self):
        self._executions: dict[str, WorkflowExecution] = {}
        self._approval_callbacks: dict[str, asyncio.Future] = {}
    
    async def execute_playbook(
        self,
        playbook: str | Path,
        alert_id: str,
        source_system: str,
        description: str = "",
        parameters: Optional[dict] = None,
    ) -> str:
        """Execute a playbook from file, returning mission_id."""
        pb = workflow_compiler.load_playbook(playbook)
        
        legacy_pb = pb.to_legacy() if isinstance(pb, type(pb)) and hasattr(pb, 'to_legacy') else pb
        
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
        )
        self._executions[mission.mission_id] = execution
        
        asyncio.create_task(self._run_workflow(mission.mission_id, pb))
        
        return mission.mission_id
    
    async def _run_workflow(self, mission_id: str, playbook: Any) -> None:
        execution = self._executions[mission_id]
        mission = mission_manager.get(mission_id)
        
        try:
            mission_manager.update_status(mission_id, MissionStatus.executing)
            
            nodes = workflow_compiler.compile(playbook)
            
            result = await self._execute_dag_with_approvals(mission_id, nodes)
            
            execution.completed_at = datetime.utcnow()
            execution.status = "completed" if not result.get("errors") else "failed"
            execution.node_results = result.get("results", {})
            execution.node_errors = result.get("errors", {})
            
            final_status = MissionStatus.completed if not result.get("errors") else MissionStatus.failed
            mission_manager.update_status(mission_id, final_status)
            
        except Exception as e:
            logger.exception(f"Workflow execution failed for mission {mission_id}")
            execution.status = "failed"
            execution.completed_at = datetime.utcnow()
            execution.node_errors["workflow"] = str(e)
            mission_manager.update_status(mission_id, MissionStatus.failed)
    
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
            for task_id in ready[:dag_executor._max_concurrency]:
                node = nodes[task_id]
                node.status = "running"
                execution.current_node = task_id
                task = asyncio.create_task(self._execute_node_with_approval(node, mission, results, semaphore))
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
        
        future = asyncio.get_event_loop().create_future()
        self._approval_callbacks[approval_id] = future
        
        try:
            decision = await asyncio.wait_for(future, timeout=approval_config.get("timeout_minutes", 30) * 60)
            node.result = {"approval_id": approval_id, "status": decision}
            if decision == "approved":
                node.status = "completed"
            else:
                node.status = "failed"
                node.error = f"Approval {decision}"
        except asyncio.TimeoutError:
            node.status = "failed"
            node.error = "Approval timeout"
        finally:
            execution.approvals_pending.pop(approval_id, None)
            self._approval_callbacks.pop(approval_id, None)
    
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
            
            result = eval(condition, {"__builtins__": {}}, context)
            
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
            branch_results.append({
                "id": branch['id'],
                "result": branch_node.result,
                "status": branch_node.status,
            })
        
        node.result = {"branches": branch_results}
        node.status = "completed" if all(b["status"] == "completed" for b in branch_results) else "failed"
    
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
            logger.exception(f"Subgraph {subgraph_name} execution failed")
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
            agents = agent_registry.get_by_role(node.role)
            if agents:
                agent = agents[0]
        
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
                    await asyncio.sleep(2 ** attempt)
        
        node.status = "failed"
    
    def respond_to_approval(self, approval_id: str, decision: str) -> bool:
        """Callback for approval response."""
        future = self._approval_callbacks.get(approval_id)
        if future and not future.done():
            future.set_result(decision)
            return True
        return False
    
    def get_execution_status(self, mission_id: str) -> Optional[WorkflowExecution]:
        return self._executions.get(mission_id)


workflow_engine = WorkflowEngine()