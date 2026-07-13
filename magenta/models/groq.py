"""Groq model client."""

from datetime import datetime

import httpx

from magenta.exceptions import ModelError
from magenta.models.base import BaseModelClient, ModelRequest, ModelResponse


class GroqClient(BaseModelClient):
    def __init__(self, model: str = "mixtral-8x7b-32768", api_key: str | None = None):
        super().__init__(model=model, provider="groq")
        self.api_key = api_key or ""
        self.base_url = "https://api.groq.com/openai/v1"

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.api_key:
            raise ModelError("Groq API key not configured")

        start = datetime.utcnow()
        messages = request.messages

        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        elapsed = (datetime.utcnow() - start).total_seconds() * 1000
        choice = data["choices"][0]

        return ModelResponse(
            content=choice["message"].get("content", ""),
            model=data.get("model", self.model),
            provider=self.provider,
            tokens_in=data.get("usage", {}).get("prompt_tokens", 0),
            tokens_out=data.get("usage", {}).get("completion_tokens", 0),
            latency_ms=elapsed,
        )

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
