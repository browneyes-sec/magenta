#!/usr/bin/env python3
"""Validate TOML configs and JSON schemas."""

import json
import sys
import tomllib
from pathlib import Path


def validate_toml():
    """Validate all TOML config files."""
    config_dir = Path("soa/config")
    if not config_dir.exists():
        print("Config directory not found")
        return True

    for f in config_dir.rglob("*.toml"):
        try:
            with open(f, "rb") as fp:
                tomllib.load(fp)
            print(f"OK {f}")
        except Exception as e:
            print(f"ERROR {f}: {e}")
            return False
    return True


def validate_json_schemas():
    """Validate all JSON schema files."""
    schema_dir = Path("soa/config")
    if not schema_dir.exists():
        print("Schema directory not found")
        return True

    for f in schema_dir.rglob("*.schema.json"):
        try:
            with open(f) as fp:
                json.load(fp)
            print(f"OK {f}")
        except Exception as e:
            print(f"ERROR {f}: {e}")
            return False
    return True


if __name__ == "__main__":
    ok = True
    ok = validate_toml() and ok
    ok = validate_json_schemas() and ok
    sys.exit(0 if ok else 1)
