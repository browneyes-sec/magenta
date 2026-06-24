"""OLLAMA model client."""

from datetime import datetime

import httpx

from magenta.models.base import BaseModelClient, ModelRequest, ModelResponse


class OllamaClient(BaseModelClient):
    def __init__(self, model: str = "qwen2.5:7b", host: str = "http://localhost:11434"):
        super().__init__(model=model, provider="ollama")
        self.host = host.rstrip("/")

    async def generate(self, request: ModelRequest) -> ModelResponse:
        start = datetime.utcnow()
        messages = request.messages

        if request.system:
            messages = [{"role": "system", "content": request.system}] + messages

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.host}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        elapsed = (datetime.utcnow() - start).total_seconds() * 1000

        return ModelResponse(
            content=data.get("message", {}).get("content", ""),
            model=self.model,
            provider=self.provider,
            tokens_in=data.get("prompt_eval_count", 0),
            tokens_out=data.get("eval_count", 0),
            latency_ms=elapsed,
        )

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.host}/api/tags")
                return response.status_code == 200
        except Exception:
            return False


class OllamaEmbeddingClient:
    """OLLAMA embedding model client."""

    def __init__(self, model: str = "all-minilm:l6-v2", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host.rstrip("/")

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.host}/api/embeddings", json={
                "model": self.model,
                "prompt": text,
            })
            response.raise_for_status()
            return response.json().get("embedding", [])

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.host}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
