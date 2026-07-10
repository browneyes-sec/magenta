"""Base model client interface."""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass


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
    system: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 2048
    tools: Optional[list[dict]] = None
    sensitivity_level: str = "LOW"  # "HIGH" | "MEDIUM" | "LOW"
    priority: str = "interactive"    # "interactive" | "batch"


class BaseModelClient(ABC):
    """Abstract base for all LLM model providers."""

    def __init__(self, model: str, provider: str):
        self.model = model
        self.provider = provider

    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelResponse: ...

    @abstractmethod
    async def ping(self) -> bool: ...
