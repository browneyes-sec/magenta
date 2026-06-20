"""Triage Agent — Alert assessment, severity assignment, initial routing."""

from typing import Any
from magenta.agents.base import LLMAgent
from magenta.core.models import (
    Mission, AgentConfig, ActionStatus, SeverityLevel,
)
from magenta.core.mission import mission_manager


class TriageAgent(LLMAgent):
    """Assesses incoming alerts, assigns severity, and routes."""
    sensitivity_level = "medium"
    task_type = "triage"

    def __init__(self, config: AgentConfig):
        config.instructions = config.instructions or """You are a Triage Agent in a SOC environment.
Assess incoming alerts and assign severity (1-5):
1 = Informational, 2 = Low, 3 = Medium, 4 = High, 5 = Critical
Route based on severity and alert type."""
        super().__init__(config)

    async def _process_impl(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        alert_desc = context.get("description", mission.description)

        # RAG context injected by BaseAgent.process() (ADR-018)
        rag_context = context.get("rag_context", "")

        prompt = f"""Assess this security alert:
Alert ID: {mission.alert_id}
Description: {alert_desc}
Source: {mission.source_system.value}

{rag_context}

Provide:
1. Severity level (1-5)
2. Likely MITRE ATT&CK tactics
3. Recommended next steps"""

        response = await self.llm_generate(prompt, tier="speed")

        result = {
            "agent": self.role,
            "verdict": response.content,
            "severity": mission.severity.value,
            "model": response.model,
            "latency_ms": response.latency_ms,
        }

        await self.log_activity(
            mission, "triage", ActionStatus.succeeded,
            tenant_id=context.get("tenant_id", "default"),
        )
        return result


class EnrichAgent(LLMAgent):
    """Enrichment Agent — adds context from CMDB, threat intel, identity."""
    sensitivity_level = "medium"
    task_type = "enrich"

    def __init__(self, config: AgentConfig):
        config.instructions = config.instructions or """You are an Enrichment Agent.
Gather context from CMDB, threat intel platforms, and identity systems.
Correlate IoCs, check asset criticality, and expand the picture."""
        super().__init__(config)

    async def _process_impl(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        # RAG context injected by BaseAgent.process() (ADR-018)
        rag_context = context.get("rag_context", "")

        prompt = f"""Enrich this security incident with context:
Alert ID: {mission.alert_id}
Description: {mission.description}
Severity: {mission.severity.value}

{rag_context}

Provide:
1. Asset criticality assessment
2. Threat intel correlations
3. Identity context
4. Expanded IoC list"""

        response = await self.llm_generate(prompt, tier="speed")

        result = {
            "agent": self.role,
            "enrichment": response.content,
            "model": response.model,
        }

        await self.log_activity(
            mission, "enrich", ActionStatus.succeeded,
            tenant_id=context.get("tenant_id", "default"),
        )
        return result


class ContainAgent(LLMAgent):
    """Containment Agent — executes isolation, disable, block actions."""
    sensitivity_level = "high"
    task_type = "contain"

    def __init__(self, config: AgentConfig):
        config.instructions = config.instructions or """You are a Containment Specialist.
Execute containment actions: disable accounts, isolate hosts, block IoCs.
Assess blast radius and risk before acting.
Require approval for actions with risk score > 60."""
        super().__init__(config)

    async def _process_impl(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        # RAG context injected by BaseAgent.process() (ADR-018)
        rag_context = context.get("rag_context", "")

        prompt = f"""Determine containment actions for this incident:
Alert ID: {mission.alert_id}
Description: {mission.description}
Risk Score: {mission.risk_score}

{rag_context}

List actions with risk scores and whether each needs approval."""

        response = await self.llm_generate(prompt, tier="speed")

        result = {
            "agent": self.role,
            "containment_plan": response.content,
            "requires_approval": mission.risk_score > 60,
        }

        await self.log_activity(
            mission, "contain", ActionStatus.succeeded,
            tenant_id=context.get("tenant_id", "default"),
        )
        return result


class InvestigateAgent(LLMAgent):
    """Investigation Agent — deep forensic analysis, timeline reconstruction."""
    sensitivity_level = "medium"
    task_type = "investigate"

    def __init__(self, config: AgentConfig):
        config.instructions = config.instructions or """You are a Forensic Investigator.
Build detailed timelines, reconstruct attack paths, extract IoCs.
Use deep reasoning to identify root cause and scope."""
        super().__init__(config)

    async def _process_impl(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        # RAG context injected by BaseAgent.process() (ADR-018)
        rag_context = context.get("rag_context", "")

        prompt = f"""Investigate this security incident in depth:
Alert ID: {mission.alert_id}
Description: {mission.description}
Previous findings: {context}

{rag_context}

Provide:
1. Attack timeline
2. Root cause analysis
3. Full IoC list
4. Scope assessment"""
        response = await self.llm_generate(prompt, tier="reasoning")
        result = {"agent": self.role, "investigation": response.content}
        await self.log_activity(
            mission, "investigate", ActionStatus.succeeded,
            tenant_id=context.get("tenant_id", "default"),
        )
        return result


class ComplianceAgent(LLMAgent):
    """Compliance Agent — ensures regulatory compliance, preserves audit trail."""
    sensitivity_level = "medium"
    task_type = "compliance"

    def __init__(self, config: AgentConfig):
        config.instructions = config.instructions or """You are a Compliance Agent.
Check all actions against regulatory frameworks (SOC2, ISO27001, NIS2).
Ensure evidence is preserved and audit trail is complete."""
        super().__init__(config)

    async def _process_impl(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        # RAG context injected by BaseAgent.process() (ADR-018)
        rag_context = context.get("rag_context", "")

        prompt = f"Review compliance implications for incident {mission.alert_id}...\nFindings: {context}\n\n{rag_context}"
        response = await self.llm_generate(prompt, tier="cost_save")
        result = {"agent": self.role, "compliance": response.content}
        await self.log_activity(
            mission, "compliance", ActionStatus.succeeded,
            tenant_id=context.get("tenant_id", "default"),
        )
        return result


class ReportAgent(LLMAgent):
    """Reporting Agent — generates incident summaries and stakeholder briefs."""
    sensitivity_level = "low"
    task_type = "report"

    def __init__(self, config: AgentConfig):
        config.instructions = config.instructions or """You are a Reporting Agent.
Generate clear, concise incident summaries for different stakeholders:
SOC analysts, management, business unit leads. Include KPIs."""
        super().__init__(config)

    async def _process_impl(self, mission: Mission, context: dict[str, Any]) -> dict[str, Any]:
        # RAG context injected by BaseAgent.process() (ADR-018)
        rag_context = context.get("rag_context", "")

        prompt = f"Generate incident summary report for {mission.alert_id}...\nAll findings: {context}\n\n{rag_context}"
        response = await self.llm_generate(prompt, tier="cost_save")
        result = {"agent": self.role, "report": response.content}
        await self.log_activity(
            mission, "report", ActionStatus.succeeded,
            tenant_id=context.get("tenant_id", "default"),
        )
        return result
