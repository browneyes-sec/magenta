"""Export OpenAPI spec from FastAPI app to static YAML file.

Usage:
    python scripts/export_openapi.py [--output docs/api/openapi.yaml]

This script creates the FastAPI app, extracts the auto-generated OpenAPI
schema, and writes it to a static YAML file for version control and
client generation.
"""

import json
import sys
from pathlib import Path

import yaml


def export_openapi(output_path: str = "docs/api/openapi.yaml") -> None:
    """Export the OpenAPI schema from the FastAPI app."""
    from magenta.api.server import create_app

    app = create_app()
    schema = app.openapi()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w") as f:
        yaml.dump(schema, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"OpenAPI spec exported to {output} ({output.stat().st_size} bytes)")

    json_output = output.with_suffix(".json")
    with open(json_output, "w") as f:
        json.dump(schema, f, indent=2, default=str)

    print(f"OpenAPI spec (JSON) exported to {json_output}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "docs/api/openapi.yaml"
    export_openapi(path)
