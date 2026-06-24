"""Automation rules engine — evaluates YAML rules against alerts."""

from typing import Any

import yaml


class RuleEngine:
    """Evaluates routing rules and triggers for automation decisions."""

    def __init__(self):
        self._rules: list[dict] = []
        self._triggers: list[dict] = []

    def load_rules(self, path: str) -> None:
        """Load rules from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
            self._rules = data.get("rules", [])

    def add_rule(self, rule: dict) -> None:
        self._rules.append(rule)

    def evaluate(self, alert: dict) -> list[dict]:
        """Evaluate all rules against an alert and return matching actions."""
        matches = []
        for rule in self._rules:
            if self._match_condition(rule.get("condition", {}), alert):
                matches.append({
                    "rule": rule.get("name", "unknown"),
                    "action": rule.get("action"),
                    "priority": rule.get("priority", 0),
                })
        return sorted(matches, key=lambda m: m["priority"], reverse=True)

    def _match_condition(self, condition: dict, alert: dict) -> bool:
        """Match a single condition against an alert."""
        field = condition.get("field", "")
        operator = condition.get("operator", "equals")
        value = condition.get("value")

        alert_value = self._get_nested(alert, field)
        if alert_value is None:
            return False

        if operator == "equals":
            return alert_value == value
        elif operator == "contains":
            return value in str(alert_value)
        elif operator == "gt":
            return float(alert_value) > float(value)
        elif operator == "lt":
            return float(alert_value) < float(value)
        elif operator == "in":
            return str(alert_value) in value if isinstance(value, list) else False
        return False

    def _get_nested(self, data: dict, path: str) -> Any:
        """Get nested value from dict using dot notation."""
        keys = path.split(".")
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None
        return data

    def list_rules(self) -> list[dict]:
        return self._rules

    def remove_rule(self, name: str) -> bool:
        for i, rule in enumerate(self._rules):
            if rule.get("name") == name:
                self._rules.pop(i)
                return True
        return False

    def add_trigger(self, trigger: dict) -> None:
        self._triggers.append(trigger)

    def list_triggers(self) -> list[dict]:
        return self._triggers


rule_engine = RuleEngine()
