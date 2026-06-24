#!/usr/bin/env python3
"""Check deviation log for open deviations count."""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DEVIATION_LOG = REPO_ROOT / "architecture" / "DEVIATION_LOG.md"


def check_deviations(max_open: int) -> int:
    if not DEVIATION_LOG.exists():
        print(f"WARNING: Deviation log not found at {DEVIATION_LOG}")
        print("Creating empty deviation log...")
        DEVIATION_LOG.write_text(
            "# Deviation Log\n\n| ID | Date | Description | Status | Owner |\n|----|------|-------------|--------|-------|\n"
        )
        return 0

    content = DEVIATION_LOG.read_text()
    open_count = content.count("| Open |") + content.count("| open |") + content.count("| OPEN |")

    if open_count > max_open:
        print(f"FAIL: {open_count} open deviations (max allowed: {max_open})")
        return 1

    print(f"OK: {open_count} open deviations (max allowed: {max_open})")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-open", type=int, default=3, help="Maximum allowed open deviations")
    args = parser.parse_args()
    sys.exit(check_deviations(args.max_open))


if __name__ == "__main__":
    main()
