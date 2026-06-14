# ADR-008: CI/FinOps Gates as SDLC Enforcers

**Status:** Accepted  
**Date:** 2026-06-14  
**Authors:** Platform Architecture Team  
**Deciders:** Platform Architecture, FinOps  

---

## Context

Cloud costs are the #1 operational risk for multi-cloud platforms. Magenta's 65/25/10 cost split ($3,000–$5,000/month) requires proactive governance. Without automated gates, the following scenarios are likely:

- A developer provisions a `Standard_NC96ads_A100_v4` GPU instance in dev ($12/hr) and forgets to tear it down.
- Untagged resources get deployed, breaking cost allocation reporting.
- Terraform drift accumulates silently until production breaks.
- Budget thresholds are exceeded before anyone notices.

Traditional approaches (manual review, monthly FinOps meetings, post-hoc cost reports) are too slow for a CI-driven SDLC.

---

## Decision

Implement **three CI gates** that run automatically on every PR touching infrastructure:

### Gate 1: Infracost (terraform-ci.yml)
- Runs `infracost breakdown` on every PR modifying `soa/terraform/`.
- Posts a cost diff comment to the PR: "+$45.23/month" or "-$120.00/month".
- **No hard block**: costs are informational — the team learns cost awareness without CI friction.

### Gate 2: Tag Compliance (finops-gate.yml)
- Queries Azure Resource Graph and AWS Tagging API for untagged resources.
- **Hard block**: fails if >5 non-compliant resources (prevents tag drift).
- Required tags: `environment`, `cost-center`, `owner`, `project`.

### Gate 3: Drift Detection (terraform-ci.yml, scheduled)
- Runs `terraform plan -detailed-exitcode` weekly via cron.
- No hard block (scheduled, not PR-gated) — creates a GitHub issue if drift is detected.
- Issues are tagged `drift` and `infrastructure` for triage.

### Additional: Budget Enforcement (finops-gate.yml, scheduled)
- Checks Azure consumption budget daily (weekdays at 08:00 UTC).
- Alerts via Slack webhook at 50%/80%/95% thresholds.
- At 95% forecasted, `enable_block_threshold` flags resources for review.

---

## Consequences

### Positive
- Every PR has a cost impact number — engineers learn to optimize.
- Tag compliance is enforced at merge time, not audit time.
- Drift is detected within 7 days (max) instead of months.
- Budget alerts arrive before the bill spike, not after.

### Negative
- CI pipelines take longer (Infracost adds ~30s, tag compliance adds ~20s).
- Azure Resource Graph queries require a service principal with Reader permissions on the root management group.
- False positives on tag compliance (ephemeral resources with no tags) require manual override.

### Risks
- Infracost API key management — mitigated by using the free tier (no API key needed) and pinning CLI version.
- Tag compliance API rate limits on large accounts — mitigated by filtering to `project = magenta` scope.
- Slack webhook token leaks — mitigated by GitHub Actions secrets and CODEOWNERS review on workflow changes.

---

## Compliance

Enforced by:
- **Workflow files**: `.github/workflows/terraform-ci.yml` and `.github/workflows/finops-gate.yml`.
- **PR template**: checklist includes "Infracost attached", "Tag compliance checked".
- **Budget module**: `soa/terraform/modules/budget/` creates the Azure budgets that the CI gate checks against.
- **Tag schema**: `soa/config/finops.toml` defines `required_tags` — the single source of truth for tag compliance rules.
- **Slack integration**: `finops-gate.yml` posts weekly cost summaries to `#finops` channel via `SLACK_FINOPS_WEBHOOK`.

---

## Notes

- Future: add `infracost comment github` behavior update to replace old comments rather than posting new ones.
- All gates are documented in the top-level `kustomization.yaml` config map for discoverability.
