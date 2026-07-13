"""Base model client interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ModelResponse:
    content: str
    model: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    tool_calls: list[dict] | None = None


@dataclass
class ModelRequest:
    messages: list[dict]
    system: str | None = None
    temperature: float = 0.2
    max_tokens: int = 2048
    tools: list[dict] | None = None
    correlation_id: str = ""
    task_type: str = "generic"
    sensitivity_level: str = "low"
    priority: str = "interactive"
    redaction_policy: dict | None = None
    max_cost_usd: float = 0.0


@dataclass
class AuditRecord:
    correlation_id: str
    task_type: str
    sensitivity_level: str
    priority: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    fallback_used: bool
    redacted: bool
    risk_score: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PolicyDecision:
    provider: str
    model: str
    fallback_providers: list[str] = field(default_factory=list)
    redaction_enabled: bool = False
    redaction_fields: list[str] = field(default_factory=list)
    max_retries: int = 3
    requires_approval: bool = False


class BaseModelClient(ABC):
    """Abstract base for all LLM model providers."""

    def __init__(self, model: str, provider: str):
        self.model = model
        self.provider = provider

    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelResponse: ...

    @abstractmethod
    async def ping(self) -> bool: ...
