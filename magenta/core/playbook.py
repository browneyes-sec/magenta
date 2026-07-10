"""Playbook parsing, validation, and management."""

from __future__ import annotations
from pathlib import Path
from typing import Any, Optional
import yaml
import json

from magenta.core.models import Playbook
from magenta.exceptions import PlaybookError


class PlaybookManager:
    """Manage playbook lifecycle: validate, register, list, remove, resolve."""

    def __init__(self):
        self._playbooks: dict[str, Playbook] = {}
        self._routing_rules: list[dict] = []
        self._default_rule: dict = {}

    async def load_routing_rules(
        self, path: str | Path = "config/routing-rules.yaml"
    ) -> None:
        """Load SOAR routing rules from a YAML file.

        Rules map alert types → playbook names with risk thresholds.
        """
        path = Path(path)
        if not path.exists():
            self._routing_rules = []
            self._default_rule = {"playbook": "Default_Investigation"}
            return

        raw = path.read_text()
        data = yaml.safe_load(raw)
        self._routing_rules = data.get("rules", [])
        self._default_rule = data.get("default", {"playbook": "Default_Investigation"})

    async def resolve(
        self,
        alert_type: str = "",
        severity: int = 0,
        risk_score: int = 0,
    ) -> dict:
        """Resolve the best routing rule for a given alert.

        Returns a dict with playbook_name, risk_score_threshold, etc.
        Falls through to default if no rule matches.
        """
        best_match = None
        best_severity_overlap = -1

        for rule in self._routing_rules:
            rule_severity = rule.get("severity_min", 1)
            # Match if alert type matches and severity >= threshold
            if rule.get("alert_type", "").lower() == alert_type.lower():
                if severity >= rule_severity:
                    overlap = len(set(rule.get("tags", [])))
                    if overlap > best_severity_overlap:
                        best_severity_overlap = overlap
                        best_match = rule

        if best_match:
            return {
                "playbook_name": best_match["playbook"],
                "risk_score_threshold": best_match.get("risk_score_threshold", 70),
                "auto_approve_under": best_match.get("auto_approve_under", 40),
                "requires_approval": best_match.get("requires_approval", False),
                "tags": best_match.get("tags", []),
            }

        # Fallback to default
        return {
            "playbook_name": self._default_rule.get("playbook", "Default_Investigation"),
            "risk_score_threshold": self._default_rule.get("risk_score_threshold", 70),
            "auto_approve_under": self._default_rule.get("auto_approve_under", 40),
            "requires_approval": self._default_rule.get("requires_approval", False),
            "tags": self._default_rule.get("tags", ["default"]),
        }

    def load(self, path: str | Path) -> Playbook:
        """Load a playbook from a YAML or JSON file."""
        path = Path(path)
        if not path.exists():
            raise PlaybookError(f"Playbook file not found: {path}")

        raw = path.read_text()
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(raw)
        elif path.suffix == ".json":
            data = json.loads(raw)
        elif path.suffix == ".toml":
            import tomli
            data = tomli.loads(raw)
        else:
            raise PlaybookError(f"Unsupported playbook format: {path.suffix}")

        return self._parse(data)

    def _parse(self, data: dict) -> Playbook:
        """Parse raw dict into Playbook model."""
        required = ["name"]
        for field in required:
            if field not in data:
                raise PlaybookError(f"Missing required field: {field}")

        return Playbook(**data)

    def validate(self, path: str | Path) -> list[str]:
        """Validate a playbook file and return list of errors."""
        errors = []
        try:
            playbook = self.load(path)
        except PlaybookError as e:
            return [str(e)]
        except Exception as e:
            return [f"Parse error: {e}"]

        if not playbook.name.strip():
            errors.append("Playbook name cannot be empty")

        if playbook.stages:
            for i, stage in enumerate(playbook.stages):
                if "role" not in stage:
                    errors.append(f"Stage {i}: missing 'role'")

        return errors

    def register(self, playbook: Playbook) -> Playbook:
        """Register a playbook in the registry."""
        key = f"{playbook.name}:{playbook.version}"
        self._playbooks[key] = playbook
        return playbook

    def get(self, name: str, version: Optional[str] = None) -> Optional[Playbook]:
        """Get a playbook by name and optional version."""
        if version:
            return self._playbooks.get(f"{name}:{version}")
        for key, pb in self._playbooks.items():
            if key.startswith(f"{name}:"):
                return pb
        return None

    def list(self, tag: Optional[str] = None) -> list[Playbook]:
        """List all registered playbooks."""
        playbooks = list(self._playbooks.values())
        if tag:
            playbooks = [p for p in playbooks if tag in p.tags]
        return sorted(playbooks, key=lambda p: p.name)

    def remove(self, name: str, version: Optional[str] = None) -> bool:
        """Remove a playbook."""
        if version:
            key = f"{name}:{version}"
            if key in self._playbooks:
                del self._playbooks[key]
                return True
        else:
            to_delete = [k for k in self._playbooks if k.startswith(f"{name}:")]
            for k in to_delete:
                del self._playbooks[k]
            return len(to_delete) > 0
        return False


playbook_manager = PlaybookManager()
