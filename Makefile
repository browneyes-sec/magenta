.PHONY: help dev dev-mesh dev-stop dev-logs test test-unit test-integration test-coverage \
        lint lint-fix clean setup tf-init tf-fmt tf-validate tf-plan-staging tf-plan-prod \
        k8s-dev k8s-staging k8s-prod build

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# ── Help ───────────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Development ─────────────────────────────────────────────────────────────

dev: ## Start all SOA services via Docker Compose
	docker compose -f soa/docker/docker-compose.minikube.yml up --build -d

dev-mesh: ## Start data mesh services (Qdrant + OLLAMA + Redis + MinIO)
	docker compose -f data/deploy/docker-compose.yml up --build -d

dev-stop: ## Stop all services
	docker compose -f soa/docker/docker-compose.minikube.yml down
	docker compose -f data/deploy/docker-compose.yml down

dev-logs: ## Tail logs from all services
	docker compose -f soa/docker/docker-compose.minikube.yml logs -f

# ── Testing ─────────────────────────────────────────────────────────────────

test: ## Run all tests (unit + integration)
	python -m pytest tests/ magnet/ -v --tb=short

test-unit: ## Run unit tests only
	python -m pytest tests/ magnet/ -v --tb=short -m "not integration"

test-integration: ## Run integration tests only
	python -m pytest tests/ magnet/ -v --tb=short -m integration

test-coverage: ## Run tests with coverage report
	python -m pytest tests/ magnet/ -v --tb=short --cov=magenta --cov-report=term --cov-report=html

# ── Linting ─────────────────────────────────────────────────────────────────

lint: ## Run all linters
	@echo "==> Terraform fmt..."
	@cd soa/terraform && terraform fmt -check -recursive 2>/dev/null || echo "  (terraform fmt warnings)"
	@echo "==> Markdown lint..."
	@markdownlint . --ignore node_modules --ignore .git --ignore .venv 2>/dev/null || echo "  (markdownlint warnings)"
	@echo "==> YAML lint..."
	@yamllint . --ignore .git --ignore .venv 2>/dev/null || echo "  (yamllint warnings)"
	@echo "==> Ruff..."
	@ruff check . 2>/dev/null || echo "  (ruff warnings)"
	@echo "==> Done."

lint-fix: ## Auto-fix lint issues
	ruff check --fix . 2>/dev/null || true
	cd soa/terraform && terraform fmt -recursive 2>/dev/null || true

# ── Setup ───────────────────────────────────────────────────────────────────

setup: ## Bootstrap development environment
	@bash scripts/setup-dev.sh

clean: ## Clean build artifacts and caches
	rm -rf .pytest_cache .ruff_cache htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .terraform -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

# ── Terraform ───────────────────────────────────────────────────────────────

TF_DIR := soa/terraform

tf-init: ## Terraform init (no backend)
	cd $(TF_DIR) && terraform init -backend=false

tf-fmt: ## Terraform fmt check
	cd $(TF_DIR) && terraform fmt -check -recursive

tf-validate: tf-init ## Terraform validate
	cd $(TF_DIR) && terraform validate

tf-plan-staging: ## Terraform plan for staging
	cd $(TF_DIR) && terraform plan -var-file=environments/staging/terraform.tfvars

tf-plan-prod: ## Terraform plan for production
	cd $(TF_DIR) && terraform plan -var-file=environments/production/terraform.tfvars

# ── Kubernetes ──────────────────────────────────────────────────────────────

k8s-dev: ## Deploy dev overlay to current K8s context
	kubectl apply -k soa/kubernetes/overlays/dev

k8s-staging: ## Deploy staging overlay
	kubectl apply -k soa/kubernetes/overlays/staging

k8s-prod: ## Deploy production overlay
	kubectl apply -k soa/kubernetes/overlays/production

# ── Build ───────────────────────────────────────────────────────────────────

build: ## Build all Docker images
	docker compose -f soa/docker/docker-compose.minikube.yml build

build-web: ## Build web gateway image only
	docker build -t magenta/mcp-web:dev -f soa/docker/Dockerfile.web-gateway .

# ── Docker Compose (full stack) ─────────────────────────────────────────────

up: build dev-mesh ## Build and start everything
	@echo "All services started. Run 'make dev-logs' to tail logs."
