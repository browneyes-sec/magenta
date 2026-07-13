"""CACAO v2 ↔ Magenta native playbook translator.

Bidirectional translation between CACAO v2.0 (OASIS standard) and
Magenta's PlaybookV2 format. Enables interoperability with SOARCA
and other CACAO-compliant orchestrators.

CACAO v2 reference: https://docs.oasis-open.org/cacao/security-playbooks/v2.0/
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from magenta.core.models import PlaybookV2

logger = logging.getLogger(__name__)


class CACAOTranslator:
    """Bidirectional CACAO v2 ↔ Magenta playbook translator."""

    def cacao_to_magenta(self, cacao: dict) -> PlaybookV2:
        """Convert a CACAO v2 playbook to Magenta PlaybookV2.

        Maps:
          - CACAO type=playbook → PlaybookV2 with apiVersion=magenta.soar/v1
          - CACAO workflow.steps → spec.workflow.nodes
          - CACAO workflow.on_completion → spec.workflow.edges
          - CACAO variables → spec.parameters
          - CACAO playbook_metadata → metadata
        """
        metadata = self._extract_metadata(cacao)
        workflow = self._translate_workflow(cacao)
        parameters = self._translate_variables(cacao)
        governance = self._translate_governance(cacao)

        return PlaybookV2(
            apiVersion="magenta.soar/v1",
            kind="Playbook",
            metadata=metadata,
            spec={
                "trigger": self._translate_trigger(cacao),
                "parameters": parameters,
                "workflow": workflow,
                "governance": governance,
            },
        )

    def magenta_to_cacao(self, pb: PlaybookV2) -> dict:
        """Convert a Magenta PlaybookV2 to CACAO v2 JSON.

        Maps:
          - metadata → CACAO id, name, description, playbook_version
          - spec.workflow.nodes → CACAO workflow.steps
          - spec.workflow.edges → CACAO workflow.on_completion
          - spec.parameters → CACAO variables
        """
        steps, step_map = self._translate_nodes_to_steps(pb)
        self._wire_edges(steps, step_map, pb)

        return {
            "type": "playbook",
            "spec_version": "cacao-2.0",
            "id": f"playbook--{pb.metadata.get('name', 'unknown')}",
            "name": pb.metadata.get("name", ""),
            "description": pb.metadata.get("description", ""),
            "playbook_version": pb.metadata.get("version", "1.0.0"),
            "created_by": "identity--magenta-asoar",
            "created": pb.metadata.get("created", datetime.utcnow().isoformat()),
            "modified": pb.metadata.get("updated", datetime.utcnow().isoformat()),
            "labels": pb.metadata.get("tags", []),
            "workflow": {
                "type": "parallel",
                "steps": steps,
            },
            "variables": self._translate_parameters_to_variables(pb),
            "playbook_metadata": self._translate_metadata_to_cacao(pb),
        }

    # ── CACAO → Magenta ────────────────────────────────────────────────

    def _extract_metadata(self, cacao: dict) -> dict:
        return {
            "name": cacao.get("name", ""),
            "version": cacao.get("playbook_version", "1.0.0"),
            "description": cacao.get("description", ""),
            "tags": cacao.get("labels", []),
            "created": cacao.get("created", ""),
            "updated": cacao.get("modified", ""),
            "cacao_id": cacao.get("id", ""),
            "cacao_created_by": cacao.get("created_by", ""),
        }

    def _translate_trigger(self, cacao: dict) -> dict:
        trigger = cacao.get("trigger", {})
        if not trigger:
            return {"type": "manual"}
        return {
            "type": trigger.get("type", "alert"),
            "source": trigger.get("sources", []),
            "condition": trigger.get("condition", {}),
        }

    def _translate_variables(self, cacao: dict) -> dict:
        variables = cacao.get("variables", {})
        params = {}
        for var_name, var_def in variables.items():
            if isinstance(var_def, dict):
                params[var_name] = var_def.get("default", var_def.get("value", ""))
            else:
                params[var_name] = var_def
        return params

    def _translate_workflow(self, cacao: dict) -> dict:
        workflow = cacao.get("workflow", {})
        raw_steps = workflow.get("steps", {})
        on_completion = workflow.get("on_completion", [])

        if isinstance(raw_steps, dict):
            step_items = list(raw_steps.values())
        else:
            step_items = list(raw_steps)

        nodes = []
        edges = []

        step_id_map: dict[str, str] = {}
        for i, step in enumerate(step_items):
            if isinstance(step, dict):
                step_key = step.get("id", f"step--{i}")
            else:
                step_key = f"step--{i}"
            node = self._step_to_node(step, step_key)
            nodes.append(node)
            step_id_map[step_key] = node.get("id", step_key)

        for i, step in enumerate(step_items):
            if not isinstance(step, dict):
                continue
            next_step = step.get("on_completion", "")
            source_key = step.get("id", f"step--{i}")
            source_id = step_id_map.get(source_key, source_key)
            if next_step and next_step in step_id_map:
                edges.append(
                    {
                        "source": source_id,
                        "target": step_id_map[next_step],
                    }
                )

        for completion in on_completion:
            if isinstance(completion, dict):
                source = completion.get("step_id", "")
                target = completion.get("next_step", "")
                if source and target:
                    edges.append({"source": source, "target": target})

        return {"nodes": nodes, "edges": edges}

    def _step_to_node(self, step: dict | str, fallback_id: str = "") -> dict:
        if not isinstance(step, dict):
            return {"id": fallback_id, "type": "action", "label": fallback_id}

        step_type = step.get("type", "action")
        action_type = step.get("action_type", "")

        node_type = self._map_cacao_type_to_magenta(step_type, action_type)

        node = {
            "id": fallback_id or step.get("id", f"step--{uuid4().hex[:8]}"),
            "type": node_type,
            "label": step.get("name", step.get("id", "")),
            "depends_on": [],
            "config": step.get("properties", {}),
        }

        if action_type:
            node["config"]["action_type"] = action_type

        if node_type == "agentic":
            node["config"]["model_tier"] = step.get("model_tier", "speed")

        return node

    def _map_cacao_type_to_magenta(self, step_type: str, action_type: str) -> str:
        mapping = {
            "action": "action",
            "decision": "decision",
            "parallel": "parallel",
            "serial": "agentic",
        }
        node_type = mapping.get(step_type, "agentic")

        if action_type in ("http-request", "api-call"):
            node_type = "action"
        elif action_type in ("human", "approval"):
            node_type = "approval"
        elif action_type in ("llm", "ai", "agent"):
            node_type = "agentic"

        return node_type

    def _translate_governance(self, cacao: dict) -> dict:
        governance = cacao.get("governance", {})
        return {
            "approval_required": governance.get("approval_required", []),
            "audit": governance.get("audit", {"log_all_decisions": True}),
            "compliance_frameworks": governance.get("compliance_frameworks", []),
        }

    # ── Magenta → CACAO ────────────────────────────────────────────────

    def _translate_nodes_to_steps(self, pb: PlaybookV2) -> tuple[list[dict], dict[str, str]]:
        workflow = pb.spec.get("workflow", {})
        nodes = workflow.get("nodes", [])
        steps = []
        step_map = {}

        for node in nodes:
            node_id = node.get("id", "")
            node_type = node.get("type", "agentic")
            config = node.get("config", {})

            step = self._node_to_step(node_id, node_type, config)
            steps.append(step)
            step_map[node_id] = step["id"]

        return steps, step_map

    def _node_to_step(self, node_id: str, node_type: str, config: dict) -> dict:
        cacao_type, action_type = self._map_magenta_type_to_cacao(node_type, config)

        clean_id = node_id.removeprefix("step--")
        step = {
            "id": f"step--{clean_id}",
            "type": cacao_type,
            "name": config.get("name", node_id),
            "description": config.get("description", ""),
        }

        if action_type:
            step["action_type"] = action_type

        if config:
            step["properties"] = config

        return step

    def _map_magenta_type_to_cacao(self, node_type: str, config: dict) -> tuple[str, str]:
        mapping = {
            "ingest": ("action", "http-request"),
            "agentic": ("serial", "llm"),
            "decision": ("decision", ""),
            "approval": ("action", "human"),
            "action": ("action", config.get("action_type", "http-request")),
            "publisher": ("action", "http-request"),
            "parallel": ("parallel", ""),
            "subgraph": ("serial", "llm"),
        }
        return mapping.get(node_type, ("action", ""))

    def _wire_edges(
        self,
        steps: list[dict],
        step_map: dict[str, str],
        pb: PlaybookV2,
    ) -> None:
        workflow = pb.spec.get("workflow", {})
        edges = workflow.get("edges", [])

        completion_map: dict[str, str] = {}
        for edge in edges:
            source_cacao = step_map.get(edge.get("source", ""), "")
            target_cacao = step_map.get(edge.get("target", ""), "")
            if source_cacao and target_cacao:
                completion_map[source_cacao] = target_cacao

        for step in steps:
            step_id = step.get("id", "")
            if step_id in completion_map:
                step["on_completion"] = completion_map[step_id]

    def _translate_parameters_to_variables(self, pb: PlaybookV2) -> dict:
        parameters = pb.spec.get("parameters", {})
        variables = {}
        for key, value in parameters.items():
            variables[key] = {
                "type": type(value).__name__ if isinstance(value, (int, float, bool)) else "string",
                "default": value,
            }
        return variables

    def _translate_metadata_to_cacao(self, pb: PlaybookV2) -> dict:
        gov = pb.spec.get("governance", {})
        cost_limits = gov.get("cost_limits", {})
        sla = gov.get("sla", {})
        return {
            "severity": gov.get("severity", "medium"),
            "cost_limit_usd": cost_limits.get("max_usd", 0),
            "max_duration_minutes": sla.get("max_minutes", 60),
        }
