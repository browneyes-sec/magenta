# Contributing to Magenta

Thank you for contributing to Magenta ASOAR. This document describes the development workflow, conventions, and standards.

## Branch Strategy

```
main              # Production releases — protected, merges from staging only
staging           # Integration branch — all PRs merge here
feature/*         # New features — branch from staging, PR to staging
fix/*             # Bug fixes — branch from staging, PR to staging
docs/*            # Documentation changes — branch from staging, PR to staging
```

**Rules:**
- No direct commits to `main` or `staging`.
- All changes go through PRs with at least one reviewer.
- `staging` is the source of truth for active development.
- Releases are tagged from `main` using semver (`v0.1.0`, `v0.2.0`, etc.).

## Commit Convention

All commits must follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body with motivation and rationale]
```

**Types:** `feat`, `fix`, `docs`, `infra`, `refactor`, `test`, `chore`
**Scopes:** `agent-ops`, `terraform`, `k8s`, `config`, `finops`, `docs`, `ci`, `adr`, `docker`

**Examples:**
```
feat(agent-ops): add finops_forecast tool with Prophet backend
fix(terraform): correct AKS subnet_id variable type
docs(adr): add ADR-008 for CI FinOps gates
infra(ci): add drift detection schedule to terraform-ci.yml
refactor(k8s): extract mcp-finops to dedicated namespace
```

## PR Workflow

1. **Branch**: `git checkout -b feature/my-feature staging`
2. **Develop**: Make changes, commit with Conventional Commits.
3. **Lint**: Run `make lint` locally before pushing.
4. **Test**: Run `make test` and ensure all tests pass.
5. **Push**: `git push origin feature/my-feature`
6. **PR**: Open a pull request to `staging` with:

   **PR template checklist:**
   - [ ] Terraform `fmt` and `validate` pass
   - [ ] Documentation updated (docs, ADR, AGENTS.md if needed)
   - [ ] ADR added for architecture decisions
   - [ ] Infracost attached (if terraform changes)
   - [ ] Tag compliance checked (if cloud resources added)
   - [ ] Conventional Commits used

7. **Review**: At least one maintainer must approve.
8. **Merge**: Squash-merge to `staging` with a clean commit message.

## Local Development Setup

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed setup instructions.

**Quick start:**
```bash
make setup        # uv sync, pre-commit install, terraform init
make dev          # docker compose up SOA services
make test         # run all tests
```

## Code Style

- **Python**: Follow PEP 8, use type hints, max line length 100. Ruff enforces these.
- **Terraform**: Use `terraform fmt` — 2-space indent, aligned `=` signs.
- **YAML/TOML**: 2-space indent, no tabs, trailing newline.
- **Dockerfiles**: Multi-stage builds, pin base image versions, use `hadolint`.
- **Markdown**: 120 char line wrap, no HTML unless necessary.

## Architecture Decisions

Any significant architectural change requires an ADR (Architecture Decision Record):

1. Create `architecture/ADR/ADR-{NNN}-{slug}.md` using the MADR template.
2. Reference the ADR in the PR description.
3. Add the ADR to the index in `AGENTS.md`.

## Security

- Never commit secrets, API keys, or certificates to the repository.
- Use Azure Workload Identity for cloud authentication (not static credentials).
- Report vulnerabilities to `security@magenta.local`.
- All PRs are scanned for secrets by the `config_analyze` tool.
