"""Chaos scenarios — pre-defined fault injection scenarios."""

from chaos_engineering.scenarios.agent_failure import AgentFailureScenario
from chaos_engineering.scenarios.directive_flood import DirectiveFloodScenario
from chaos_engineering.scenarios.mission_timeout import MissionTimeoutScenario
from chaos_engineering.scenarios.model_degradation import ModelDegradationScenario
from chaos_engineering.scenarios.pipeline_backpressure import PipelineBackpressureScenario
from chaos_engineering.scenarios.registry_poison import RegistryPoisonScenario

SCENARIO_REGISTRY = {
    "agent_failure": AgentFailureScenario,
    "directive_flood": DirectiveFloodScenario,
    "model_degradation": ModelDegradationScenario,
    "mission_timeout": MissionTimeoutScenario,
    "registry_poison": RegistryPoisonScenario,
    "pipeline_backpressure": PipelineBackpressureScenario,
}
