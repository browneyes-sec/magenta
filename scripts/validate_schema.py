#!/usr/bin/env python3
"""Validate AutomationActivity schema version matches expected."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EXPECTED_VERSION = "1.0"


def validate():
    sys.path.insert(0, str(REPO_ROOT))
    from magenta.core.models import AutomationActivity

    version_field = AutomationActivity.model_fields.get("schema_version")
    if not version_field:
        print("ERROR: schema_version field not found in AutomationActivity")
        return 1

    actual_version = version_field.default
    if actual_version != EXPECTED_VERSION:
        print(f"ERROR: Schema version mismatch: expected {EXPECTED_VERSION}, got {actual_version}")
        return 1

    print(f"OK: AutomationActivity schema_version = {actual_version}")
    return 0


if __name__ == "__main__":
    sys.exit(validate())