"""Workflow Compiler - Compiles YAML/Graph playbooks to executable DAG."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from magenta.core.models import (
    Playbook,
    PlaybookV2,
    SubgraphSpec,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeType,
    WorkflowSpec,
)
from magenta.exceptions import PlaybookError
from magenta.orchestration.dag_executor import DAGNode

logger = logging.getLogger(__name__)


class WorkflowCompiler:
    """Compiles Magenta playbooks (v1 legacy or v2 native) into executable DAGs."""

    def __init__(self):
        self._subgraph_registry: dict[str, SubgraphSpec] = {}
        self._node_type_handlers = {
            WorkflowNodeType.ingest: self._compile_ingest_node,
            WorkflowNodeType.agentic: self._compile_agentic_node,
            WorkflowNodeType.decision: self._compile_decision_node,
            WorkflowNodeType.approval: self._compile_approval_node,
            WorkflowNodeType.action: self._compile_action_node,
            WorkflowNodeType.publisher: self._compile_publisher_node,
            WorkflowNodeType.parallel: self._compile_parallel_node,
            WorkflowNodeType.subgraph: self._compile_subgraph_node,
        }

    def compile(self, playbook: Playbook | PlaybookV2 | str | Path) -> dict[str, DAGNode]:
        """Compile a playbook into a DAG of executable nodes."""
        if isinstance(playbook, (str, Path)):
            playbook = self.load_playbook(playbook)

        if isinstance(playbook, PlaybookV2):
            spec = self._parse_v2_spec(playbook)
        else:
            spec = self._parse_legacy_spec(playbook)

        self._register_subgraphs(spec)
        nodes = self._build_dag_nodes(spec)
        self._validate_dag(nodes)

        return nodes

    def load_playbook(self, path: str | Path) -> Playbook | PlaybookV2:
        """Load playbook from YAML/JSON file (v1 or v2 format)."""
        path = Path(path)
        if not path.exists():
            raise PlaybookError(f"Playbook file not found: {path}")

        raw = path.read_text()
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(raw)
        elif path.suffix == ".json":
            data = json.loads(raw)
        else:
            raise PlaybookError(f"Unsupported format: {path.suffix}")

        if data.get("apiVersion", "").startswith("magenta.soar"):
            return PlaybookV2(**data)
        return Playbook(**data)

    def _parse_v2_spec(self, pb: PlaybookV2) -> WorkflowSpec:
        spec_data = pb.spec
        workflow = spec_data.get("workflow", {})
        edges = [WorkflowEdge(**e) for e in workflow.get("edges", [])]

        edge_map: dict[str, list[str]] = {}
        for edge in edges:
            edge_map.setdefault(edge.target, []).append(edge.source)

        nodes = []
        for raw_node in workflow.get("nodes", []):
            node_id = raw_node.get("id", "")
            extra_depends = raw_node.get("depends_on", [])
            all_depends = list(set(edge_map.get(node_id, []) + extra_depends))
            raw_node["depends_on"] = all_depends
            nodes.append(WorkflowNode(**raw_node))

        return WorkflowSpec(
            nodes=nodes,
            edges=edges,
            parameters=spec_data.get("parameters", {}),
        )

    def _parse_legacy_spec(self, pb: Playbook) -> WorkflowSpec:
        stages = pb.stages or []
        nodes = []
        edges = []

        for i, stage in enumerate(stages):
            node_id = stage.get("task_id", f"stage_{i}")
            role = stage.get("role", "triage")
            depends_on = stage.get("depends_on", [])
            params = stage.get("params", {})

            node_type = WorkflowNodeType.agentic
            if role == "ingest":
                node_type = WorkflowNodeType.ingest

            nodes.append(
                WorkflowNode(
                    id=node_id,
                    type=node_type,
                    label=stage.get("name", node_id),
                    agent=role,
                    depends_on=depends_on,
                    config=params,
                )
            )

            for dep in depends_on:
                edges.append(WorkflowEdge(source=dep, target=node_id))

        if not nodes:
            nodes.append(
                WorkflowNode(
                    id="triage",
                    type=WorkflowNodeType.agentic,
                    agent="triage",
                )
            )

        return WorkflowSpec(nodes=nodes, edges=edges, parameters={})

    def _register_subgraphs(self, spec: WorkflowSpec) -> None:
        pass

    def _build_dag_nodes(self, spec: WorkflowSpec) -> dict[str, DAGNode]:
        nodes = {}

        for wf_node in spec.nodes:
            handler = self._node_type_handlers.get(wf_node.type)
            if not handler:
                logger.warning(f"No handler for node type: {wf_node.type}")
                handler = self._compile_agentic_node

            dag_node = handler(wf_node, spec.parameters)
            nodes[wf_node.id] = dag_node

        return nodes

    def _compile_ingest_node(self, node: WorkflowNode, params: dict) -> DAGNode:
        return DAGNode(
            task_id=node.id,
            role=node.agent or "ingest",
            depends_on=node.depends_on,
            params={**node.config, **params, "node_type": "ingest"},
        )

    def _compile_agentic_node(self, node: WorkflowNode, params: dict) -> DAGNode:
        config = {**node.config, **params, "node_type": "agentic"}
        if node.subgraph:
            config["subgraph"] = node.subgraph

        return DAGNode(
            task_id=node.id,
            role=node.agent or "triage",
            depends_on=node.depends_on,
            params=config,
        )

    def _compile_decision_node(self, node: WorkflowNode, params: dict) -> DAGNode:
        return DAGNode(
            task_id=node.id,
            role="decision",
            depends_on=node.depends_on,
            params={**node.config, **params, "node_type": "decision", "condition": node.condition},
        )

    def _compile_approval_node(self, node: WorkflowNode, params: dict) -> DAGNode:
        return DAGNode(
            task_id=node.id,
            role="approval",
            depends_on=node.depends_on,
            params={**node.config, **params, "node_type": "approval"},
        )

    def _compile_action_node(self, node: WorkflowNode, params: dict) -> DAGNode:
        return DAGNode(
            task_id=node.id,
            role=node.agent or "action",
            depends_on=node.depends_on,
            params={**node.config, **params, "node_type": "action"},
        )

    def _compile_publisher_node(self, node: WorkflowNode, params: dict) -> DAGNode:
        return DAGNode(
            task_id=node.id,
            role="publisher",
            depends_on=node.depends_on,
            params={**node.config, **params, "node_type": "publisher"},
        )

    def _compile_parallel_node(self, node: WorkflowNode, params: dict) -> DAGNode:
        p = {**node.config, **params, "node_type": "parallel"}
        p["branches"] = node.config.get("branches", [])
        return DAGNode(
            task_id=node.id,
            role="parallel",
            depends_on=node.depends_on,
            params=p,
        )

    def _compile_subgraph_node(self, node: WorkflowNode, params: dict) -> DAGNode:
        p = {**node.config, **params, "node_type": "subgraph"}
        p["subgraph_name"] = node.subgraph
        return DAGNode(
            task_id=node.id,
            role="subgraph",
            depends_on=node.depends_on,
            params=p,
        )

    def _validate_dag(self, nodes: dict[str, DAGNode]) -> None:
        from collections import defaultdict, deque

        in_degree = defaultdict(int)
        graph = defaultdict(list)

        for task_id, node in nodes.items():
            for dep in node.depends_on:
                if dep not in nodes:
                    logger.warning(f"Task {task_id} depends on unknown task {dep}")
                graph[dep].append(task_id)
                in_degree[task_id] += 1
            if task_id not in in_degree:
                in_degree[task_id] = 0

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
            raise PlaybookError("Playbook DAG contains cycles")


workflow_compiler = WorkflowCompiler()
