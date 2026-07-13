#!/usr/bin/env bash
set -euo pipefail

MAGENTA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MAGENTA_DIR"

echo "==> Magenta Dev Setup"
echo ""

# ── Python / uv ────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "[1/6] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | bash
    export PATH="$HOME/.cargo/bin:$PATH"
else
    echo "[1/6] uv already installed ($(uv --version))"
fi

echo "[2/6] Syncing Python dependencies..."
uv sync --group dev --group finops

# ── Pre-commit ─────────────────────────────────────────────────────────────
echo "[3/6] Installing pre-commit hooks..."
uv tool run pre-commit install --install-hooks 2>/dev/null || \
    uv run pre-commit install --install-hooks

# ── Terraform ──────────────────────────────────────────────────────────────
if command -v terraform &>/dev/null; then
    echo "[4/6] Terraform init (no backend)..."
    cd soa/terraform
    terraform init -backend=false 2>/dev/null && echo "  init ok" || echo "  (skipped)"
    cd "$MAGENTA_DIR"
else
    echo "[4/6] terraform not found — skipping init (install via: tfenv or asdf)"
fi

# ── Docker Compose ─────────────────────────────────────────────────────────
echo "[5/6] Pulling Docker base images..."
docker pull python:3.12-slim 2>/dev/null || echo "  (will pull on build)"

# ── Environment check ──────────────────────────────────────────────────────
echo "[6/6] Verifying environment..."

check_tool() {
    if command -v "$1" &>/dev/null; then
        echo "  ✓ $1 $($1 --version 2>&1 | head -1)"
    else
        echo "  ✗ $1 — not found (optional)"
    fi
}

check_tool python3
check_tool docker
check_tool terraform
check_tool kubectl
check_tool minikube

echo ""
echo "==> Setup complete."
echo "    Next steps:"
echo "      source .venv/bin/activate   # or use 'uv run' directly"
echo "      make dev                     # start SOA services"
echo "      make test                    # run tests"
