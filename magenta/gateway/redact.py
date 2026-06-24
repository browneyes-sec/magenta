import re

from magenta.models.base import ModelRequest

PII_PATTERNS: dict[str, str] = {
    "usernames": r"(?i)\b(?:user(?:name)?|login|handle)[=:]\s*\S+",
    "ips": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "email_addresses": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "hostnames": r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b",
    "phone_numbers": r"\b\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b",
    "credit_cards": r"\b(?:\d[ -]*?){13,16}\b",
    "api_keys": r"(?i)\b(?:api[_-]?key|apikey|secret|token)[=:]\s*\S+",
}


class RedactionLayer:
    def __init__(self, enabled: bool = True, default_fields: list[str] | None = None):
        self.enabled = enabled
        self.default_fields = default_fields or ["usernames", "ips", "email_addresses"]

    async def apply(self, request: ModelRequest) -> ModelRequest:
        if not self.enabled:
            return request

        fields = self.default_fields[:]
        if request.redaction_policy:
            fields = request.redaction_policy.get("fields", fields)

        import copy
        redacted = copy.deepcopy(request)

        for i, msg in enumerate(redacted.messages):
            if isinstance(msg.get("content"), str):
                msg["content"] = self._redact_text(msg["content"], fields)

        if isinstance(redacted.system, str):
            redacted.system = self._redact_text(redacted.system, fields)

        return redacted

    def _redact_text(self, text: str, fields: list[str]) -> str:
        for field in fields:
            pattern = PII_PATTERNS.get(field)
            if pattern:
                text = re.sub(pattern, f"[REDACTED:{field}]", text)
        return text
