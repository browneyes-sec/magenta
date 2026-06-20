"""Playbook parsing, validation, and management."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import yaml
import json

from magenta.core.models import Playbook
from magenta.exceptions import PlaybookError


class PlaybookManager:
    """Manage playbook lifecycle: validate, register, list, remove."""

    def __init__(self):
        self._playbooks: dict[str, Playbook] = {}

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
        """Get a playbook by name and optional version.

        When version is None, returns the latest registered version.
        """
        if version:
            return self._playbooks.get(f"{name}:{version}")
        matching = [
            (v, pb)
            for k, pb in self._playbooks.items()
            if k.startswith(f"{name}:")
            for v in [k.split(":", 1)[1]]
        ]
        if not matching:
            return None
        matching.sort(key=lambda t: t[0], reverse=True)
        return matching[0][1]

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
