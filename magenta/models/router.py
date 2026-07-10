"""Tiered model router with fallback chains."""

from __future__ import annotations
from typing import Optional, Any
from datetime import datetime
import random

from magenta.models.base import BaseModelClient, ModelRequest, ModelResponse
from magenta.models.ollama import OllamaClient
from magenta.models.openrouter import OpenRouterClient
from magenta.models.gemini import GeminiClient
from magenta.models.groq import GroqClient
from magenta.config import settings
from magenta.exceptions import ModelError, ModelTimeout


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

    def get_client(self, name: str) -> Optional[BaseModelClient]:
        return self._clients.get(name)

    async def route(
        self,
        request: ModelRequest,
        tier: str = "speed",
        max_attempts: int = 3,
    ) -> ModelResponse:
        """Route a request through the model tier with fallback.

        Policy enforcement (llm-policy.md):
            - HIGH sensitivity → Ollama-only (no external egress)
            - MEDIUM sensitivity → local preferred, hosted allowed with policy override
            - LOW sensitivity → normal routing by tier
        """
        # ─── POLICY: HIGH-sensitivity → Ollama-only ──────────────────────
        if request.sensitivity_level == "HIGH":
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
        client_names = tier_config["clients"]
        random.shuffle(client_names)  # load balance

        for attempt in range(max_attempts):
            for name in client_names:
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

                    return response

                except (ModelError, ModelTimeout, Exception) as e:
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

    def get_available_models(self) -> list[dict]:
        """Get list of all configured models."""
        return [
            {"name": name, "provider": c.provider, "model": c.model}
            for name, c in self._clients.items()
        ]


model_router = ModelRouter()
