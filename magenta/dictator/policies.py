"""Dictator orchestration policies — rules that govern how agents are deployed and missions run."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class OrchestrationPolicy(BaseModel):
    """A named policy that constrains or guides orchestration decisions."""

    name: str
    description: str = ""
    rules: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    priority: int = 100

    def applies_to(self, mission) -> bool:
        if not self.enabled:
            return False
        rule_trigger = self.rules.get("trigger", {})
        if not rule_trigger:
            return True
        if "severity_min" in rule_trigger and mission.severity.value < rule_trigger["severity_min"]:
            return False
        if "severity_max" in rule_trigger and mission.severity.value > rule_trigger["severity_max"]:
            return False
        if "risk_min" in rule_trigger and mission.risk_score < rule_trigger["risk_min"]:
            return False
        return True


DEFAULT_POLICIES = [
    OrchestrationPolicy(
        name="default_pipeline",
        description="Low-severity alerts run in fast pipeline mode",
        priority=200,
        rules={
            "teaming": "pipeline",
            "trigger": {"severity_max": 2},
            "probes": {"triage": True, "report": True},
            "auto_approve": True,
        },
    ),
    OrchestrationPolicy(
        name="standard_supervisor",
        description="Medium severity: supervisor teaming with enrich + report",
        priority=150,
        rules={
            "teaming": "supervisor",
            "trigger": {"severity_min": 3, "severity_max": 3},
            "probes": {"triage": True, "enrich": True, "report": True},
            "auto_approve": True,
        },
    ),
    OrchestrationPolicy(
        name="high_severity_debate",
        description="High severity: debate teaming with full agent suite",
        priority=100,
        rules={
            "teaming": "debate",
            "trigger": {"severity_min": 4, "severity_max": 4},
            "probes": {"triage": True, "enrich": True, "contain": True, "investigate": True, "compliance": True, "report": True},
            "auto_approve": False,
        },
    ),
    OrchestrationPolicy(
        name="critical_referee",
        description="Critical severity: referee teaming with human-in-loop approval",
        priority=50,
        rules={
            "teaming": "referee",
            "trigger": {"severity_min": 5},
            "probes": {"all": True},
            "auto_approve": False,
            "require_human": True,
        },
    ),
]


class PolicyEngine:
    """Evaluates policies against missions to determine orchestration strategy."""

    def __init__(self):
        self._policies: list[OrchestrationPolicy] = list(DEFAULT_POLICIES)
        self._overrides: dict[str, OrchestrationPolicy] = {}

    def add_policy(self, policy: OrchestrationPolicy) -> None:
        self._policies.append(policy)
        self._policies.sort(key=lambda p: p.priority)

    def remove_policy(self, name: str) -> bool:
        before = len(self._policies)
        self._policies = [p for p in self._policies if p.name != name]
        return len(self._policies) < before

    def set_override(self, policy: OrchestrationPolicy) -> None:
        self._overrides[policy.name] = policy
        from magenta.dictator.state import dictator_state
        dictator_state.set_policy(policy.name, policy.model_dump())

    def clear_overrides(self) -> None:
        from magenta.dictator.state import dictator_state
        for name in list(self._overrides.keys()):
            dictator_state.clear_policy(name)
        self._overrides.clear()

    def evaluate(self, mission) -> dict[str, Any]:
        """Evaluate all applicable policies and return merged orchestration config."""
        config = {
            "teaming": "supervisor",
            "probes": {},
            "auto_approve": True,
            "require_human": False,
        }

        # Overrides take precedence
        for policy in self._overrides.values():
            if policy.applies_to(mission):
                config.update(policy.rules)

        # Apply normal policies (only if not overridden)
        for policy in self._policies:
            if policy.name in self._overrides:
                continue
            if policy.applies_to(mission):
                config.update(policy.rules)

        return config


policy_engine = PolicyEngine()
