"""Google Gemini model client."""

from datetime import datetime

import httpx

from magenta.exceptions import ModelError
from magenta.models.base import BaseModelClient, ModelRequest, ModelResponse


class GeminiClient(BaseModelClient):
    def __init__(self, model: str = "gemini-2.0-flash", api_key: str | None = None):
        super().__init__(model=model, provider="gemini")
        self.api_key = api_key or ""

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.api_key:
            raise ModelError("Gemini API key not configured")

        start = datetime.utcnow()
        contents = []

        for msg in request.messages:
            role = "user" if msg["role"] in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}],
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }

        if request.system:
            payload["systemInstruction"] = {"parts": [{"text": request.system}]}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        elapsed = (datetime.utcnow() - start).total_seconds() * 1000
        candidate = data.get("candidates", [{}])[0]
        content = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")

        return ModelResponse(
            content=content,
            model=self.model,
            provider=self.provider,
            tokens_in=data.get("usageMetadata", {}).get("promptTokenCount", 0),
            tokens_out=data.get("usageMetadata", {}).get("candidatesTokenCount", 0),
            latency_ms=elapsed,
        )

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
                )
                return response.status_code == 200
        except Exception:
            return False
