"""FastAPI LLM Gateway Service — external proxy endpoint."""

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from magenta.models.base import ModelRequest, ModelResponse
from magenta.gateway.engine import LLMGateway

app = FastAPI(title="Magenta LLM Gateway", version="0.1.0")
gateway: Optional[LLMGateway] = None


class GatewayMessage(BaseModel):
    role: str
    content: str


class GatewayRequest(BaseModel):
    messages: list[GatewayMessage]
    system: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 2048
    correlation_id: str = ""
    task_type: str = "generic"
    sensitivity_level: str = "low"
    priority: str = "interactive"


class GatewayResponse(BaseModel):
    content: str
    model: str
    provider: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    correlation_id: str


@app.on_event("startup")
async def startup():
    global gateway
    gateway = LLMGateway(mode="enforcing")
    await gateway.start()


@app.on_event("shutdown")
async def shutdown():
    if gateway:
        await gateway.stop()


@app.post("/v1/chat/completions")
async def chat_completions(req: GatewayRequest) -> GatewayResponse:
    if not gateway:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    model_req = ModelRequest(
        messages=[m.model_dump() for m in req.messages],
        system=req.system,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        correlation_id=req.correlation_id,
        task_type=req.task_type,
        sensitivity_level=req.sensitivity_level,
        priority=req.priority,
    )

    resp = await gateway.route(model_req)

    return GatewayResponse(
        content=resp.content,
        model=resp.model,
        provider=resp.provider,
        tokens_in=resp.tokens_in,
        tokens_out=resp.tokens_out,
        latency_ms=resp.latency_ms,
        correlation_id=req.correlation_id,
    )


@app.get("/admin/policy")
async def get_policy():
    if not gateway:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    return {"mode": gateway.mode, "policy_loaded": gateway._started}


@app.get("/health")
async def health():
    return {"status": "ok"}
