import os
import yaml
from pathlib import Path
from fnmatch import fnmatch
from magenta.models.base import ModelRequest, PolicyDecision


class PolicyEngine:
    def __init__(self, policy_path: str | None = None):
        self.policy_path = policy_path or os.getenv(
            "MAGENTA_POLICY_FILE", "config/llm-routing.yaml"
        )
        self._rules: list[dict] = []
        self._default: dict = {}
        self._openrouter_cfg: dict = {}
        self._loaded = False

    async def load(self) -> None:
        path = Path(self.policy_path)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {self.policy_path}")
        raw = path.read_text()
        data = yaml.safe_load(raw)
        self._rules = data.get("policies", [])
        self._default = data.get("default", {})
        self._openrouter_cfg = data.get("openrouter", {})
        self._loaded = True

    async def evaluate(self, request: ModelRequest) -> PolicyDecision:
        if not self._loaded:
            await self.load()

        match = self._find_match(request)

        routing = match.get("routing", self._default.get("routing", {}))
        providers = routing.get("providers", ["ollama"])
        preferred = routing.get("preferred", providers[0] if providers else "ollama")
        fallback = routing.get("fallback", "")

        redact_cfg = match.get("redaction", self._default.get("redaction", {}))
        redaction_enabled = redact_cfg.get("enabled", False)
        redaction_fields = redact_cfg.get("fields", [])

        quotas = match.get("quotas", self._default.get("quotas", {}))
        max_retries = quotas.get("max_retries", 3)

        if request.sensitivity_level == "high" and preferred != "ollama":
            preferred = "ollama"
            fallback = "queue"

        fallback_list: list[str] = []
        if fallback and fallback != "queue":
            fallback_list = [fallback]
        fallback_list += [p for p in providers if p != preferred]

        return PolicyDecision(
            provider=preferred,
            model=request.system or "default",
            fallback_providers=fallback_list,
            redaction_enabled=redaction_enabled,
            redaction_fields=redaction_fields,
            max_retries=max_retries,
        )

    async def fallback(self, decision: PolicyDecision) -> PolicyDecision:
        if decision.fallback_providers:
            next_provider = decision.fallback_providers[0]
            decision.provider = next_provider
            decision.fallback_providers = decision.fallback_providers[1:]
        else:
            decision.provider = "ollama"
        return decision

    def _find_match(self, request: ModelRequest) -> dict:
        best: dict | None = None
        best_score = -1

        for rule in self._rules:
            match = rule.get("match", {})
            score = 0
            total = 0

            if "sensitivity_level" in match:
                total += 1
                if match["sensitivity_level"] == request.sensitivity_level:
                    score += 1

            if "task_type" in match:
                total += 1
                if match["task_type"] == request.task_type:
                    score += 1

            if "priority" in match:
                total += 1
                if match["priority"] == request.priority:
                    score += 1

            if total > 0 and (total == score):
                rule_score = len(match.keys())
                if rule_score > best_score:
                    best_score = rule_score
                    best = rule

        return best or {}
