"""LLM Gateway — policy evaluation, redaction, routing, audit chain."""


from magenta.exceptions import ModelError
from magenta.gateway.audit import AuditLogger
from magenta.gateway.cache import SemanticCache
from magenta.gateway.policy import PolicyEngine
from magenta.gateway.ratelimit import CircuitBreaker, TokenBucket
from magenta.gateway.redact import RedactionLayer
from magenta.models.base import ModelRequest, ModelResponse, PolicyDecision
from magenta.models.router import ModelRouter, model_router


class LLMGateway:
    def __init__(
        self,
        policy: PolicyEngine | None = None,
        redact: RedactionLayer | None = None,
        ratelimit: TokenBucket | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        audit: AuditLogger | None = None,
        cache: SemanticCache | None = None,
        router: ModelRouter | None = None,
        mode: str = "shadow",
    ):
        self.policy = policy or PolicyEngine()
        self.redact = redact or RedactionLayer()
        self.ratelimit = ratelimit or TokenBucket()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.audit = audit or AuditLogger()
        self.cache = cache or SemanticCache()
        self.router = router or model_router
        self.mode = mode  # "shadow" | "enforcing"
        self._started = False

    async def start(self) -> None:
        if not self._started:
            await self.policy.load()
            await self.audit.start()
            self._started = True

    async def stop(self) -> None:
        await self.audit.stop()

    async def route(self, request: ModelRequest) -> ModelResponse:
        if not self._started:
            await self.start()

        cached = await self.cache.get(request)
        if cached:
            return cached

        decision: PolicyDecision = await self.policy.evaluate(request)

        fallback_used = False
        redacted = False

        if decision.provider != "ollama" and decision.redaction_enabled:
            if self.mode == "enforcing" or self.redact.enabled:
                request = await self.redact.apply(request)
                redacted = True

        if await self.circuit_breaker.is_open(decision.provider):
            decision = await self._try_fallback(decision)
            fallback_used = True

        if not await self.ratelimit.consume(decision.provider):
            await self.ratelimit.wait(decision.provider)

        response = await self._execute(decision, request)

        await self.cache.set(request, response)
        await self.audit.log(request, response, decision, fallback_used, redacted)

        return response

    async def _execute(self, decision: PolicyDecision, request: ModelRequest) -> ModelResponse:
        for attempt in range(decision.max_retries):
            try:
                if decision.provider == "ollama":
                    response = await self.router.route(request, tier="speed")
                else:
                    response = await self._route_via_provider(decision, request)

                await self.circuit_breaker.record_success(decision.provider)
                return response

            except ModelError:
                await self.circuit_breaker.record_failure(decision.provider)
                if attempt < decision.max_retries - 1:
                    decision = await self.policy.fallback(decision)
                    continue
                raise

        raise ModelError(f"All providers exhausted for {request.correlation_id}")

    async def _route_via_provider(
        self, decision: PolicyDecision, request: ModelRequest
    ) -> ModelResponse:
        provider_tier_map = {
            "openrouter": "cost_save",
            "gemini": "cost_save",
            "groq": "cost_save",
        }
        tier = provider_tier_map.get(decision.provider, "speed")
        return await self.router.route(request, tier=tier)

    async def _try_fallback(self, decision: PolicyDecision) -> PolicyDecision:
        return await self.policy.fallback(decision)
