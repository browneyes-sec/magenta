"""Configuration analysis tools — config_analyze, config_validate, config_diff.

Supports TOML, YAML, JSON, and HCL formats. Validates against JSON Schema
registry. Scans for security issues (secrets), deprecated keys, and
best-practice violations.
"""

from __future__ import annotations

import difflib
import json
import re
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
import tomli
import yaml

logger = structlog.get_logger(__name__)

# Patterns flagged by --checks security
SECRET_PATTERNS: list[tuple[str, str]] = [
    ("aws_access_key", r"(?i)aws_access_key_id\s*[=:]\s*['\"]?AKIA[0-9A-Z]{16}"),
    ("azure_connection_string", r"(?i)(connection_string|conn_string)\s*[=:]\s*['\"]?DefaultEndpointsProtocol="),
    ("private_key", r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----"),
    ("api_token", r"(?i)(api[_-]?key|api[_-]?token|secret|password)\s*[=:]\s*['\"].{8,}['\"]"),
    ("generic_token", r"(?i)(token|secret)\s*[=:]\s*['\"][A-Za-z0-9_\-\.]{20,}['\"]"),
]

# Deprecated keys flagged by --checks deprecation
DEPRECATED_KEYS: dict[str, list[str]] = {
    "system.toml": ["old_service_registry", "legacy_auth_mode"],
    "providers.toml": ["azure_classic", "aws_iam_user"],
    "finops.toml": ["legacy_budget"],
}


class ConfigAnalyzer:
    """Analyzes configuration files for correctness, security, and compliance."""

    def __init__(self, schema_dir: str | Path = ""):
        self.schema_dir = Path(schema_dir) if schema_dir else Path("soa/config/schemas")
        self.schemas: dict[str, dict] = {}
        self._load_schemas()

    def _load_schemas(self):
        if not self.schema_dir.exists():
            return
        for f in self.schema_dir.glob("*.schema.json"):
            try:
                with open(f) as fh:
                    self.schemas[f.stem.replace(".schema", "")] = json.load(fh)
            except Exception as e:
                logger.warning("Failed to load schema", file=str(f), error=str(e))

    def analyze(self, path: str, fmt: str = "toml", checks: list[str] | None = None) -> dict:
        """Analyze config files matching a glob pattern."""
        checks = checks or ["syntax", "schema"]
        base = Path(path)
        if not base.exists():
            return {"files_analyzed": 0, "errors": [f"Path not found: {path}"], "warnings": [], "summary": {}}

        pattern = f"*.{fmt}" if base.is_dir() else base.name
        search_dir = base if base.is_dir() else base.parent
        files = sorted(search_dir.rglob(pattern)) if search_dir.is_dir() else [base]

        results = {"files_analyzed": 0, "errors": [], "warnings": [], "summary": {}}
        for file in files:
            if file.is_dir():
                continue
            result = self._analyze_file(file, checks)
            results["files_analyzed"] += 1
            results["errors"].extend(result["errors"])
            results["warnings"].extend(result["warnings"])

        results["summary"] = {
            "total_errors": len(results["errors"]),
            "total_warnings": len(results["warnings"]),
            "checks_applied": checks,
        }
        return results

    def _analyze_file(self, file: Path, checks: list[str]) -> dict:
        errors, warnings = [], []
        try:
            data = self._parse_file(file)
        except Exception as e:
            return {"errors": [{"file": str(file), "check": "syntax", "message": str(e)}], "warnings": []}

        if "syntax" in checks:
            pass  # success if _parse_file didn't raise

        if "schema" in checks:
            schema_key = file.stem
            if schema_key in self.schemas:
                try:
                    import jsonschema
                    jsonschema.validate(instance=data, schema=self.schemas[schema_key])
                except ImportError:
                    warnings.append({"file": str(file), "check": "schema", "message": "jsonschema not installed"})
                except jsonschema.ValidationError as e:
                    errors.append({"file": str(file), "check": "schema", "message": e.message, "path": list(e.path)})

        if "security" in checks:
            text = file.read_text()
            for name, pattern in SECRET_PATTERNS:
                if re.search(pattern, text):
                    warnings.append({"file": str(file), "check": "security", "message": f"Possible {name} detected"})

        if "deprecation" in checks:
            for config_name, keys in DEPRECATED_KEYS.items():
                if config_name in file.name:
                    for key in keys:
                        if self._key_exists(data, key):
                            warnings.append({"file": str(file), "check": "deprecation", "message": f"Deprecated key: {key}"})

        if "best_practice" in checks:
            if isinstance(data, dict) and "version" not in data:
                warnings.append({"file": str(file), "check": "best_practice", "message": "Missing version field"})
            if isinstance(data, dict) and "name" not in data:
                warnings.append({"file": str(file), "check": "best_practice", "message": "Missing name field"})

        return {"errors": errors, "warnings": warnings}

    def validate(self, file_path: str, schema_ref: str = "") -> dict:
        """Validate a single config file against a schema."""
        file = Path(file_path)
        if not file.exists():
            return {"valid": False, "errors": [f"File not found: {file_path}"]}
        try:
            data = self._parse_file(file)
        except Exception as e:
            return {"valid": False, "errors": [str(e)]}

        schema_key = schema_ref or file.stem
        schema = self.schemas.get(schema_key)
        if not schema:
            return {"valid": True, "errors": [], "note": f"No schema found for {schema_key}"}

        try:
            import jsonschema
            jsonschema.validate(instance=data, schema=schema)
            return {"valid": True, "errors": []}
        except ImportError:
            return {"valid": False, "errors": ["jsonschema not installed"]}
        except jsonschema.ValidationError as e:
            return {"valid": False, "errors": [e.message]}

    def diff(self, current: str, target: str, fmt: str = "unified") -> dict:
        """Diff two configuration files."""
        cur_path, tgt_path = Path(current), Path(target)
        if not cur_path.exists():
            return {"error": f"Current file not found: {current}"}
        if not tgt_path.exists():
            return {"error": f"Target file not found: {target}"}

        cur_text = cur_path.read_text()
        tgt_text = tgt_path.read_text()

        diff_lines = list(difflib.unified_diff(
            cur_text.splitlines(keepends=True),
            tgt_text.splitlines(keepends=True),
            fromfile=str(cur_path),
            tofile=str(tgt_path),
        ))

        return {
            "files": {"current": str(cur_path), "target": str(tgt_path)},
            "format": fmt,
            "changes": len(diff_lines),
            "diff": "".join(diff_lines),
        }

    def _parse_file(self, path: Path) -> Any:
        """Parse a config file based on its extension."""
        suffix = path.suffix.lower()
        text = path.read_text()
        if suffix in (".toml",):
            return tomli.loads(text)
        elif suffix in (".yaml", ".yml"):
            return yaml.safe_load(text) or {}
        elif suffix in (".json",):
            return json.loads(text)
        elif suffix in (".hcl", ".tf"):
            return {"_raw_hcl": text, "_note": "HCL parsing requires hcl2 parser"}
        else:
            raise ValueError(f"Unsupported format: {suffix}")

    def _key_exists(self, data: Any, dotted_key: str) -> bool:
        """Check if a dotted key path exists in nested dict."""
        parts = dotted_key.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        return True
