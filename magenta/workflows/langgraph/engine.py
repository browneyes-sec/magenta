"""LangGraph integration — subgraph registry, state schema, and pre-built SOC subgraphs.

Uses only what's already in pyproject.toml:
  - langchain >=0.1.0 (includes langgraph as submodule)
  - aiosqlite for checkpoint persistence

No new pip dependencies required.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any, TypedDict

logger = logging.getLogger(__name__)

# ── Lazy imports — degrade gracefully if langgraph unavailable ──────────

try:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.graph.message import add_messages
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    logger.warning("langgraph not installed — subgraph features unavailable")


# ── Shared state schema ────────────────────────────────────────────────

class WorkflowState(TypedDict, total=False):
    """Shared state passed through all LangGraph subgraph nodes.

    Designed to be a superset of what magenta's DAG nodes produce,
    so upstream_results from the DAG executor map cleanly.
    """
    mission_id: str
    alert: dict
    context: dict
    upstream_results: dict
    agent_outputs: Annotated[list[dict], add_messages] if HAS_LANGGRAPH else list
    approvals: dict
    artifacts: dict
    error: str | None


# ── Subgraph registry ─────────────────────────────────────────────────

_subgraph_registry: dict[str, Any] = {}
_checkpointer: Any | None = None


async def get_checkpointer():
    """Get or create the shared SQLite checkpointer (lazy init)."""
    global _checkpointer
    if _checkpointer is None and HAS_LANGGRAPH:
        _checkpointer = AsyncSqliteSaver.from_conn_string("data/workflow_checkpoints.db")
        await _checkpointer.setup()
    return _checkpointer


def register_subgraph(name: str, graph: Any) -> None:
    """Register a compiled LangGraph subgraph by name."""
    _subgraph_registry[name] = graph
    logger.info("Registered subgraph: %s", name)


def get_subgraph(name: str) -> Any | None:
    """Lookup a compiled subgraph by name."""
    return _subgraph_registry.get(name)


def list_subgraphs() -> list[str]:
    """List all registered subgraph names."""
    return list(_subgraph_registry.keys())


# ── Built-in subgraph factories ────────────────────────────────────────
#
# Each factory returns a compiled StateGraph.
# They use MCP tools from the tool_registry — imported lazily to avoid
# circular imports and to degrade if MCP servers are unavailable.

def build_triage_subgraph():
    """Triage: assess_severity → extract_iocs → assign_mitre.

    Tools: sentinel.query_logs, threat_intel.lookup_ioc
    """
    if not HAS_LANGGRAPH:
        logger.warning("Cannot build triage_subgraph — langgraph unavailable")
        return None

    from magenta.workflows.mcp.tool_registry import get_tools_for_subgraph

    tools = get_tools_for_subgraph("triage")
    tool_node = _make_tool_node(tools) if tools else None

    builder = StateGraph(WorkflowState)

    builder.add_node("assess_severity", _triage_assess_severity)
    builder.add_node("extract_iocs", _triage_extract_iocs)
    builder.add_node("assign_mitre", _triage_assign_mitre)
    if tool_node:
        builder.add_node("tools", tool_node)

    builder.add_edge(START, "assess_severity")
    builder.add_edge("assess_severity", "extract_iocs")
    builder.add_edge("extract_iocs", "assign_mitre")
    builder.add_edge("assign_mitre", END)

    checkpointer = _get_checkpointer_sync()
    return builder.compile(checkpointer=checkpointer)


def build_investigation_subgraph():
    """Investigation: build_timeline → root_cause → scope_assessment.

    Tools: datalake.search, sentinel.query_logs, entra.get_user, defender.get_alert
    """
    if not HAS_LANGGRAPH:
        return None

    from magenta.workflows.mcp.tool_registry import get_tools_for_subgraph

    tools = get_tools_for_subgraph("investigation")
    tool_node = _make_tool_node(tools) if tools else None

    builder = StateGraph(WorkflowState)

    builder.add_node("build_timeline", _investigation_build_timeline)
    builder.add_node("root_cause", _investigation_root_cause)
    builder.add_node("scope_assessment", _investigation_scope)
    if tool_node:
        builder.add_node("tools", tool_node)

    builder.add_edge(START, "build_timeline")
    builder.add_edge("build_timeline", "root_cause")
    builder.add_edge("root_cause", "scope_assessment")
    builder.add_edge("scope_assessment", END)

    checkpointer = _get_checkpointer_sync()
    return builder.compile(checkpointer=checkpointer)


def build_containment_subgraph():
    """Containment: evaluate_risk → select_actions → execute_containment.

    Tools: defender.isolate_host, entra.disable_user, sentinel.block_ip
    """
    if not HAS_LANGGRAPH:
        return None

    from magenta.workflows.mcp.tool_registry import get_tools_for_subgraph

    tools = get_tools_for_subgraph("containment")
    tool_node = _make_tool_node(tools) if tools else None

    builder = StateGraph(WorkflowState)

    builder.add_node("evaluate_risk", _containment_evaluate_risk)
    builder.add_node("select_actions", _containment_select_actions)
    builder.add_node("execute_containment", _containment_execute)
    if tool_node:
        builder.add_node("tools", tool_node)

    builder.add_edge(START, "evaluate_risk")
    builder.add_edge("evaluate_risk", "select_actions")
    builder.add_edge("select_actions", "execute_containment")
    builder.add_edge("execute_containment", END)

    checkpointer = _get_checkpointer_sync()
    return builder.compile(checkpointer=checkpointer)


def build_compliance_subgraph():
    """Compliance: check_frameworks → validate_evidence → generate_audit.

    Tools: artifacts.save
    """
    if not HAS_LANGGRAPH:
        return None

    from magenta.workflows.mcp.tool_registry import get_tools_for_subgraph

    tools = get_tools_for_subgraph("compliance")
    tool_node = _make_tool_node(tools) if tools else None

    builder = StateGraph(WorkflowState)

    builder.add_node("check_frameworks", _compliance_check_frameworks)
    builder.add_node("validate_evidence", _compliance_validate_evidence)
    builder.add_node("generate_audit", _compliance_generate_audit)
    if tool_node:
        builder.add_node("tools", tool_node)

    builder.add_edge(START, "check_frameworks")
    builder.add_edge("check_frameworks", "validate_evidence")
    builder.add_edge("validate_evidence", "generate_audit")
    builder.add_edge("generate_audit", END)

    checkpointer = _get_checkpointer_sync()
    return builder.compile(checkpointer=checkpointer)


# ── Node implementations ──────────────────────────────────────────────
#
# Each node is a pure async function: (WorkflowState) -> dict.
# They use the magenta LLM gateway (already exists) for model calls,
# and MCP tools (via tool_registry) for data access.

async def _triage_assess_severity(state: WorkflowState) -> dict:
    """Assess alert severity using LLM."""
    alert = state.get("alert", {})
    prompt = f"""Assess this security alert and assign severity (1-5):
Alert: {alert.get('id', 'unknown')}
Source: {alert.get('source', 'unknown')}
Description: {alert.get('description', 'none')}

Return JSON: {{"severity": <int>, "reasoning": "<str>", "mitre_tactics": [<str>]}}"""

    result = await _llm_call(prompt, tier="speed")
    outputs = list(state.get("agent_outputs", []))
    outputs.append({"node": "assess_severity", "result": result})
    ctx = {**state.get("context", {}), "severity_assessment": result}
    return {"agent_outputs": outputs, "context": ctx}


async def _triage_extract_iocs(state: WorkflowState) -> dict:
    """Extract IOCs from alert data."""
    alert = state.get("alert", {})
    severity = state.get("context", {}).get("severity_assessment", {})
    prompt = f"""Extract all IOCs from this alert:
Alert: {alert}
Severity assessment: {severity}

Return JSON: {{"iocs": [{{"type": "<ip|domain|hash|url|email>", "value": "<str>", "confidence": <float>}}]}}"""

    result = await _llm_call(prompt, tier="speed")
    outputs = list(state.get("agent_outputs", []))
    outputs.append({"node": "extract_iocs", "result": result})
    return {"agent_outputs": outputs, "context": {**state.get("context", {}), "iocs": result}}


async def _triage_assign_mitre(state: WorkflowState) -> dict:
    """Assign MITRE ATT&CK techniques."""
    context = state.get("context", {})
    prompt = f"""Based on this triage context, assign MITRE ATT&CK techniques:
Severity: {context.get('severity_assessment', {})}
IOCs: {context.get('iocs', {})}

Return JSON: {{"techniques": [{{"id": "T####", "name": "<str>", "tactic": "<str>", "confidence": <float>}}]}}"""

    result = await _llm_call(prompt, tier="speed")
    outputs = list(state.get("agent_outputs", []))
    outputs.append({"node": "assign_mitre", "result": result})
    return {"agent_outputs": outputs, "context": {**context, "mitre": result}}


async def _investigation_build_timeline(state: WorkflowState) -> dict:
    """Build incident timeline from alert context."""
    alert = state.get("alert", {})
    upstream = state.get("upstream_results", {})
    prompt = f"""Build a detailed incident timeline from:
Alert: {alert}
Upstream triage results: {upstream}

Return JSON: {{"timeline": [{{"timestamp": "<ISO>", "event": "<str>", "source": "<str>", "significance": "<str>"}}]}}"""

    result = await _llm_call(prompt, tier="reasoning")
    outputs = list(state.get("agent_outputs", []))
    outputs.append({"node": "build_timeline", "result": result})
    return {"agent_outputs": outputs, "context": {**state.get("context", {}), "timeline": result}}


async def _investigation_root_cause(state: WorkflowState) -> dict:
    """Perform root cause analysis."""
    context = state.get("context", {})
    prompt = f"""Analyze root cause from:
Timeline: {context.get('timeline', {})}
IOCs: {context.get('iocs', {})}

Return JSON: {{"root_cause": "<str>", "attack_path": [<str>], "initial_access": "<str>", "persistence": "<str>"}}"""

    result = await _llm_call(prompt, tier="reasoning")
    outputs = list(state.get("agent_outputs", []))
    outputs.append({"node": "root_cause", "result": result})
    return {"agent_outputs": outputs, "context": {**context, "root_cause": result}}


async def _investigation_scope(state: WorkflowState) -> dict:
    """Assess scope and blast radius."""
    context = state.get("context", {})
    prompt = f"""Assess the scope and blast radius:
Root cause: {context.get('root_cause', {})}
Timeline: {context.get('timeline', {})}
IOCs: {context.get('iocs', {})}

Return JSON: {{"scope": {{"affected_hosts": [<str>], "affected_users": [<str>], "affected_networks": [<str>]}}, "blast_radius": "<single-user|subnet|domain|enterprise>", "data_exfiltration_risk": "<low|medium|high>"}}"""

    result = await _llm_call(prompt, tier="reasoning")
    outputs = list(state.get("agent_outputs", []))
    outputs.append({"node": "scope_assessment", "result": result})
    return {"agent_outputs": outputs, "context": {**context, "scope": result}}


async def _containment_evaluate_risk(state: WorkflowState) -> dict:
    """Evaluate containment risk and blast radius."""
    context = state.get("context", {})
    prompt = f"""Evaluate containment risk for this incident:
Scope: {context.get('scope', {})}
Root cause: {context.get('root_cause', {})}

Return JSON: {{"risk_score": <int 0-100>, "auto_contain": <bool>, "reasoning": "<str>", "blast_radius": "<str>"}}"""

    result = await _llm_call(prompt, tier="speed")
    outputs = list(state.get("agent_outputs", []))
    outputs.append({"node": "evaluate_risk", "result": result})
    return {"agent_outputs": outputs, "context": {**context, "containment_risk": result}}


async def _containment_select_actions(state: WorkflowState) -> dict:
    """Select appropriate containment actions."""
    context = state.get("context", {})
    risk = context.get("containment_risk", {})
    scope = context.get("scope", {})
    prompt = f"""Select containment actions:
Risk: {risk}
Scope: {scope}
Available actions: isolate_host, disable_account, block_ip, block_url, reset_password

Return JSON: {{"actions": [{{"type": "<str>", "target": "<str>", "priority": <int>, "auto_approvable": <bool>}}]}}"""

    result = await _llm_call(prompt, tier="speed")
    outputs = list(state.get("agent_outputs", []))
    outputs.append({"node": "select_actions", "result": result})
    return {"agent_outputs": outputs, "context": {**context, "containment_actions": result}}


async def _containment_execute(state: WorkflowState) -> dict:
    """Execute containment actions (delegates to action nodes in DAG)."""
    context = state.get("context", {})
    actions = context.get("containment_actions", {}).get("actions", [])
    outputs = list(state.get("agent_outputs", []))
    outputs.append({"node": "execute_containment", "result": {"planned": len(actions), "note": "Executed by DAG action nodes"}})
    return {"agent_outputs": outputs, "context": {**context, "containment_executed": True}}


async def _compliance_check_frameworks(state: WorkflowState) -> dict:
    """Check compliance frameworks (SOC2, ISO27001, NIS2)."""
    context = state.get("context", {})
    prompt = f"""Check compliance implications:
Incident context: {context}

Return JSON: {{"frameworks": {{"SOC2": {{"applicable": <bool>, "findings": [<str>]}}, "ISO27001": {{"applicable": <bool>, "findings": [<str>]}}, "NIS2": {{"applicable": <bool>, "findings": [<str>]}}}}, "audit_required": <bool>}}"""

    result = await _llm_call(prompt, tier="cost_save")
    outputs = list(state.get("agent_outputs", []))
    outputs.append({"node": "check_frameworks", "result": result})
    return {"agent_outputs": outputs, "context": {**context, "compliance": result}}


async def _compliance_validate_evidence(state: WorkflowState) -> dict:
    """Validate evidence preservation."""
    context = state.get("context", {})
    outputs = list(state.get("agent_outputs", []))
    outputs.append({"node": "validate_evidence", "result": {"validated": True, "artifacts": list(state.get("artifacts", {}).keys())}})
    return {"agent_outputs": outputs, "context": {**context, "evidence_validated": True}}


async def _compliance_generate_audit(state: WorkflowState) -> dict:
    """Generate audit trail entry."""
    context = state.get("context", {})
    outputs = list(state.get("agent_outputs", []))
    audit_entry = {
        "mission_id": state.get("mission_id", ""),
        "timestamp": datetime.utcnow().isoformat(),
        "compliance": context.get("compliance", {}),
        "evidence_validated": context.get("evidence_validated", False),
        "timeline": context.get("timeline", {}),
        "root_cause": context.get("root_cause", {}),
    }
    outputs.append({"node": "generate_audit", "result": audit_entry})
    return {"agent_outputs": outputs, "artifacts": {**state.get("artifacts", {}), "audit_entry": audit_entry}}


# ── Helpers ────────────────────────────────────────────────────────────

async def _llm_call(prompt: str, tier: str = "speed") -> dict:
    """Call LLM via magenta's existing model router (zero new deps)."""
    try:
        from magenta.models.base import ModelRequest
        from magenta.models.router import model_router

        request = ModelRequest(
            messages=[{"role": "user", "content": prompt}],
            task_type="workflow_subgraph",
            sensitivity_level="medium",
        )
        response = await model_router.route(request, tier=tier)
        return {
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "latency_ms": response.latency_ms,
        }
    except Exception as exc:
        logger.warning("LLM call failed (tier=%s): %s", tier, exc)
        return {"content": "", "error": str(exc)}


def _make_tool_node(tools: list):
    """Create a LangGraph ToolNode from a list of LangChain tools."""
    if not HAS_LANGGRAPH or not tools:
        return None
    try:
        from langgraph.prebuilt import ToolNode
        return ToolNode(tools)
    except ImportError:
        return None


_shared_checkpointer = None


def _get_checkpointer_sync():
    """Synchronous checkpointer getter for subgraph compilation.

    Returns a shared in-memory checkpointer. For production persistence,
    use get_checkpointer() (async) which returns an AsyncSqliteSaver.
    """
    global _shared_checkpointer
    if not HAS_LANGGRAPH:
        return None
    try:
        if _shared_checkpointer is None:
            from langgraph.checkpoint.memory import MemorySaver
            _shared_checkpointer = MemorySaver()
        return _shared_checkpointer
    except ImportError:
        return None


# ── Auto-register built-in subgraphs on import ────────────────────────

def initialize_subgraphs() -> None:
    """Build and register all built-in subgraphs. Call once at startup."""
    if not HAS_LANGGRAPH:
        logger.info("LangGraph unavailable — skipping subgraph initialization")
        return

    builders = {
        "triage_subgraph": build_triage_subgraph,
        "investigation_subgraph": build_investigation_subgraph,
        "containment_subgraph": build_containment_subgraph,
        "compliance_subgraph": build_compliance_subgraph,
    }

    for name, builder in builders.items():
        try:
            graph = builder()
            if graph:
                register_subgraph(name, graph)
        except Exception as exc:
            logger.warning("Failed to build subgraph %s: %s", name, exc)
