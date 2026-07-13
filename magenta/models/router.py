"""Tiered model router with fallback chains."""

from __future__ import annotations

import random
import time
from datetime import datetime

from magenta.config import settings
from magenta.exceptions import ModelError, ModelTimeout
from magenta.models.base import BaseModelClient, ModelRequest, ModelResponse, PolicyDecision
from magenta.models.gemini import GeminiClient
from magenta.models.groq import GroqClient
from magenta.models.ollama import OllamaClient
from magenta.models.openrouter import OpenRouterClient


class CircuitBreaker:
    """Simple circuit breaker per model client."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 60.0):
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    def record_success(self, client_name: str) -> None:
        self._failures.pop(client_name, None)
        self._open_until.pop(client_name, None)

    def record_failure(self, client_name: str) -> None:
        self._failures[client_name] = self._failures.get(client_name, 0) + 1
        if self._failures[client_name] >= self._failure_threshold:
            self._open_until[client_name] = time.monotonic() + self._cooldown_seconds

    def is_open(self, client_name: str) -> bool:
        open_until = self._open_until.get(client_name)
        if open_until is None:
            return False
        if time.monotonic() >= open_until:
            self._open_until.pop(client_name, None)
            return False
        return True


class ModelRouter:
    """
    Routes model requests to the appropriate provider with tiered fallback.

    Tiers:
      - speed: Small local models (OLLAMA < 8B) for real-time actions
      - reasoning: Larger models (OLLAMA 8x7B, 32B) for complex decisions
      - cost_save: Free API models (Gemini, Groq) for non-sensitive tasks
    """

    def __init__(self):
        self._clients: dict[str, BaseModelClient] = {}
        self._circuit_breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=60.0)
        self._init_clients()

    def _init_clients(self) -> None:
        cfg = settings.models

        # OLLAMA
        self._clients["ollama_qwen"] = OllamaClient("qwen2.5:7b", cfg.ollama_host)
        self._clients["ollama_mistral"] = OllamaClient("mistral:7b", cfg.ollama_host)
        self._clients["ollama_mixtral"] = OllamaClient("mixtral:8x7b", cfg.ollama_host)
        self._clients["ollama_qwen32"] = OllamaClient("qwen2.5:32b", cfg.ollama_host)
        self._clients["ollama_deepseek"] = OllamaClient("deepseek-r1:7b", cfg.ollama_host)

        # OpenRouter
        if cfg.openrouter_key:
            self._clients["openrouter_gemini"] = OpenRouterClient(
                "google/gemini-2.0-flash-001", cfg.openrouter_key
            )

        # Gemini
        if cfg.gemini_key:
            self._clients["gemini_flash"] = GeminiClient("gemini-2.0-flash", cfg.gemini_key)

        # Groq
        if cfg.groq_key:
            self._clients["groq_mixtral"] = GroqClient("mixtral-8x7b-32768", cfg.groq_key)

    TIERS = {
        "speed": {
            "clients": ["ollama_qwen", "ollama_mistral", "ollama_deepseek"],
            "fallback": "reasoning",
        },
        "reasoning": {
            "clients": ["ollama_mixtral", "ollama_qwen32", "ollama_deepseek"],
            "fallback": "cost_save",
        },
        "cost_save": {
            "clients": ["openrouter_gemini", "gemini_flash", "groq_mixtral"],
            "fallback": "speed",
        },
    }

    def get_client(self, name: str) -> BaseModelClient | None:
        return self._clients.get(name)

    async def route(
        self,
        request: ModelRequest,
        tier: str = "speed",
        max_attempts: int = 3,
    ) -> ModelResponse:
        """Route a request through the model tier with fallback.

        Policy enforcement:
            - high sensitivity -> Ollama-only (no external egress)
            - medium sensitivity -> local preferred, hosted allowed with policy override
            - low sensitivity -> normal routing by tier
        """
        sensitivity = getattr(request, "sensitivity_level", "low").lower()

        # ─── POLICY: HIGH-sensitivity -> Ollama-only ─────────────────────
        if sensitivity == "high":
            ollama_clients = {
                name: client
                for name, client in self._clients.items()
                if client.provider == "ollama"
            }
            if not ollama_clients:
                raise ModelError(
                    "HIGH-sensitivity request blocked: "
                    "no local Ollama models available. "
                    "Check Ollama configuration."
                )
            client_names = list(ollama_clients.keys())
            random.shuffle(client_names)
            for name in client_names:
                client = ollama_clients[name]
                try:
                    start = datetime.utcnow()
                    response = await client.generate(request)
                    elapsed = (datetime.utcnow() - start).total_seconds() * 1000
                    response.latency_ms = elapsed
                    return response
                except (ModelError, ModelTimeout, Exception):
                    continue
            raise ModelError(
                "HIGH-sensitivity request failed: "
                f"all {len(ollama_clients)} local Ollama models exhausted"
            )
        tier_config = self.TIERS.get(tier, self.TIERS["speed"])
        client_names = list(tier_config["clients"])  # copy to avoid mutating tier config

        if sensitivity == "high":
            client_names = [n for n in client_names if "ollama" in n]
            if not client_names:
                raise ModelError("HIGH sensitivity but no Ollama clients configured")
        elif sensitivity == "medium":
            ollama_first = [n for n in client_names if "ollama" in n]
            external = [n for n in client_names if "ollama" not in n]
            client_names = ollama_first + external

        random.shuffle(client_names)  # load balance

        for attempt in range(max_attempts):
            for name in client_names:
                if self._circuit_breaker.is_open(name):
                    continue

                client = self._clients.get(name)
                if not client:
                    continue

                try:
                    start = datetime.utcnow()
                    response = await client.generate(request)
                    elapsed = (datetime.utcnow() - start).total_seconds() * 1000

                    # Check latency threshold
                    tier_max = {"speed": 5000, "reasoning": 15000, "cost_save": 30000}
                    if elapsed > tier_max.get(tier, 10000):
                        continue

                    self._circuit_breaker.record_success(name)
                    return response

                except (ModelError, ModelTimeout, Exception):
                    self._circuit_breaker.record_failure(name)
                    continue

        # All attempts exhausted → fallback tier
        fallback_tier = tier_config.get("fallback")
        if fallback_tier and fallback_tier != tier:
            return await self.route(request, tier=fallback_tier, max_attempts=1)

        raise ModelError(f"All models in tier '{tier}' and fallbacks exhausted")

    async def ping_all(self) -> dict[str, bool]:
        """Ping all configured model clients."""
        results = {}
        for name, client in self._clients.items():
            try:
                results[name] = await client.ping()
            except Exception:
                results[name] = False
        return results

    async def route_with_policy(
        self,
        request: ModelRequest,
        decision: PolicyDecision,
    ) -> ModelResponse:
        """Route a request based on a policy decision (used by the LLM Gateway)."""

        provider_tier_map = {
            "openrouter": "cost_save",
            "gemini": "cost_save",
            "groq": "cost_save",
            "ollama": "speed",
        }
        tier = provider_tier_map.get(decision.provider, "speed")

        if decision.provider == "ollama":
            return await self.route(request, tier=tier)

        client_key = None
        for name, client in self._clients.items():
            if decision.provider in name:
                client_key = name
                break

        if client_key:
            client = self._clients[client_key]
            try:
                return await client.generate(request)
            except Exception:
                pass

        return await self.route(request, tier=tier)

    def get_available_models(self) -> list[dict]:
        """Get list of all configured models."""
        return [
            {"name": name, "provider": c.provider, "model": c.model}
            for name, c in self._clients.items()
        ]


model_router = ModelRouter()
