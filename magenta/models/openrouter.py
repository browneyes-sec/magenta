"""OpenRouter model client with multi-model fallback."""

from datetime import datetime

import httpx

from magenta.exceptions import ModelError
from magenta.models.base import BaseModelClient, ModelRequest, ModelResponse


class OpenRouterClient(BaseModelClient):
    FALLBACK_MODELS = [
        "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.3-70b-instruct",
        "mistralai/mistral-7b-instruct",
    ]

    PROVIDER_ORDER = ["Together", "Fireworks", "DeepInfra"]

    def __init__(
        self,
        model: str = "openrouter/auto",
        api_key: str | None = None,
    ):
        super().__init__(model=model, provider="openrouter")
        self.api_key = api_key or ""
        self.base_url = "https://openrouter.ai/api/v1"

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.api_key:
            raise ModelError("OpenRouter API key not configured")

        start = datetime.utcnow()
        messages = request.messages

        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages

        models = self._select_models(request)

        payload = {
            "model": self.model,
            "models": models,
            "route": "fallback",
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "provider": {"order": self.PROVIDER_ORDER},
        }

        if request.tools:
            payload["tools"] = request.tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://magenta.security",
            "X-Title": "Magenta ASOAR",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            remain = response.headers.get("X-RateLimit-Remaining-requests")
            if remain and int(remain) <= 1:
                pass

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "5")
                raise ModelError(f"Rate limited, retry after {retry_after}s")

            response.raise_for_status()
            data = response.json()

        elapsed = (datetime.utcnow() - start).total_seconds() * 1000
        choice = data["choices"][0]
        message = choice["message"]

        tokens_cost = data.get("usage", {}).get("total_cost", 0)

        return ModelResponse(
            content=message.get("content", ""),
            model=data.get("model", self.model),
            provider=self.provider,
            tokens_in=data.get("usage", {}).get("prompt_tokens", 0),
            tokens_out=data.get("usage", {}).get("completion_tokens", 0),
            latency_ms=elapsed,
            tool_calls=message.get("tool_calls"),
        )

    def _select_models(self, request: ModelRequest) -> list[str]:
        if request.redaction_policy and "models" in request.redaction_policy:
            return request.redaction_policy["models"]
        return [self.model] + self.FALLBACK_MODELS

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return response.status_code == 200
        except Exception:
            return False
