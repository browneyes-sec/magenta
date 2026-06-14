"""
LLM Policy Filter — Content redaction and sensitivity gating for Open WebUI.

Functions:
- Redact sensitive data (PII, credentials, internal names) from LLM I/O
- Gate high-sensitivity content behind approval
- Enforce content policies on model responses

Deployed as a serverless function alongside Open WebUI pipelines.
"""

import re
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SENSITIVE_PATTERNS = {
    "api_key": re.compile(r"(?i)(api[-_]?key|apikey|secret|token)\s*[=:]\s*['\"]?\w{16,}['\"]?"),
    "password": re.compile(r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"]?\S+['\"]?"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "connection_string": re.compile(r"(?i)(connectionstring|connstr)\s*[=:]\s*['\"]?\S+['\"]?"),
    "tenant_id": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
}


class SensitivityLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def redact_content(text: str, patterns: Optional[list[str]] = None) -> str:
    """Redact sensitive information from text.

    Args:
        text: The text to redact.
        patterns: List of pattern names to apply (None = all).

    Returns:
        Redacted text.
    """
    result = text
    targets = patterns or list(SENSITIVE_PATTERNS.keys())

    for name in targets:
        pattern = SENSITIVE_PATTERNS.get(name)
        if pattern:
            result = pattern.sub(f"[REDACTED:{name}]", result)

    return result


def assess_sensitivity(text: str) -> str:
    """Assess the sensitivity level of content.

    Args:
        text: Content to assess.

    Returns:
        Sensitivity level: low, medium, high, or critical.
    """
    score = 0

    for name, pattern in SENSITIVE_PATTERNS.items():
        matches = pattern.findall(text)
        score += len(matches) * 2

    connection_string_count = len(SENSITIVE_PATTERNS["connection_string"].findall(text))
    score += connection_string_count * 5

    if score >= 10:
        return SensitivityLevel.CRITICAL
    elif score >= 5:
        return SensitivityLevel.HIGH
    elif score >= 2:
        return SensitivityLevel.MEDIUM
    return SensitivityLevel.LOW


def should_gate(sensitivity: str, mode: str = "shadow") -> bool:
    """Determine if content should be gated behind approval.

    Args:
        sensitivity: Assessed sensitivity level.
        mode: Gate mode (shadow, enforcing).

    Returns:
        True if content should be gated.
    """
    if mode == "shadow":
        return False
    return sensitivity in (SensitivityLevel.HIGH, SensitivityLevel.CRITICAL)


def filter_prompt(prompt: str) -> dict:
    """Filter a prompt for sensitive content before sending to LLM.

    Args:
        prompt: The raw prompt text.

    Returns:
        Dict with filtered prompt, sensitivity, redacted_fields, and gated status.
    """
    redacted = redact_content(prompt)
    sensitivity = assess_sensitivity(prompt)
    redacted_count = sum(
        1 for p in SENSITIVE_PATTERNS.values()
        if p.search(prompt)
    )

    return {
        "filtered_prompt": redacted,
        "sensitivity": sensitivity,
        "redacted_fields_count": redacted_count,
        "gated": should_gate(sensitivity),
    }


def filter_response(response: str) -> dict:
    """Filter a model response for sensitive content before displaying.

    Args:
        response: The model response text.

    Returns:
        Dict with filtered response and redaction summary.
    """
    redacted = redact_content(response)
    return {
        "filtered_response": redacted,
        "was_redacted": redacted != response,
    }
