#!/bin/bash
# Collector sidecar entrypoint
# Validates config, waits for dependencies, starts collector runner.

set -euo pipefail

echo "=== Magenta Collector Sidecar Starting ==="
echo "Config: ${MAGENTA_CONFIG_PATH:-/config/collectors.toml}"

# Wait for Redis
if [ -n "${REDIS_URL:-}" ]; then
    echo "Waiting for Redis..."
    until redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; do
        sleep 2
    done
    echo "Redis ready"
fi

# Validate collectors.toml exists
if [ ! -f "${MAGENTA_CONFIG_PATH:-/config/collectors.toml}" ]; then
    echo "ERROR: collectors.toml not found at ${MAGENTA_CONFIG_PATH:-/config/collectors.toml}"
    exit 1
fi

# Export all MAGENTA_* env vars for Python
export PYTHONPATH="/app:${PYTHONPATH:-}"

exec "$@"
