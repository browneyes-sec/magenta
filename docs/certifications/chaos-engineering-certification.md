# Chaos Engineering Certification Guide

## Overview

Each `magenta chaos run` produces a **condensed certification report** deposited in `docs/certifications/`. This guide explains the certification lifecycle, naming conventions, and how to interpret results.

## Naming Convention

```
magenta_chaos-DD_MM_YY-NNN.md
```

| Component | Description | Example |
|---|---|---|
| `magenta_chaos` | Fixed prefix | `magenta_chaos` |
| `DD_MM_YY` | Date (day, month, 2-digit year) | `16_06_26` |
| `NNN` | Sequential run number per day | `001` |

The system auto-numbers runs per calendar day. If you run chaos 3 times on June 16, 2026, the files are:
- `magenta_chaos-16_06_26-001.md`
- `magenta_chaos-16_06_26-002.md`
- `magenta_chaos-16_06_26-003.md`

## Report Sections

### 1. Header

```
# Chaos Certification Report
Run ID:     magenta_chaos-16_06_26-001
Verdict:    ✅ PASS | ❌ FAIL | ⚠️ PARTIAL
Scenarios:  5 passed, 0 failed, 2 skipped
Duration:   47.3s
Intensity:  3
```

### 2. Scenario Results

| Scenario | Status | Recovery Time | Details |
|---|---|---|---|
| agent_failure | ✅ PASS | 1.2s | Triage recovered within SLA |
| directive_flood | ✅ PASS | 0.8s | Backpressure limited to 47 |
| model_degradation | ✅ PASS | 0.0s | Ollama fallback activated |
| mission_timeout | ✅ PASS | 2.1s | Mission cleanup succeeded |
| registry_poison | ✅ PASS | 0.3s | Rejected 100% malformed |
| pipeline_backpressure | ⏭️ SKIP | — | EventHub unavailable |
| custom | ⏭️ SKIP | — | Not configured |

### 3. Regression Results

```
Regressions: 10/12 passed (41 tests)
Status: ✅ PASS | ❌ FAIL
```

- **full** = `pytest magnet/` (all tests)
- **lightweight** = `pytest magnet/test_core/ magnet/test_agents/` (fast subset)
- **none** = No regression available (report only)

### 4. Probe Snapshot

```
Pre-chaos:   5/5 probes healthy
Post-chaos:  5/5 probes healthy
Delta:       0 failures
```

### 5. Recommendations

Organized by severity with specific action items:

- **Critical**: Immediate remediation required
- **High**: Address within 24 hours
- **Medium**: Address within 1 week
- **Low**: Address within 1 month

### 6. Verdict

| Verdict | Meaning |
|---|---|
| ✅ **PASS** | All enabled scenarios recovered, regression passed |
| ⚠️ **PARTIAL** | Some scenarios skipped or regression incomplete |
| ❌ **FAIL** | One or more scenarios failed or regression failed |

## Interpreting Results

### Healthy System (PASS)

A PASS verdict means:
- All injected faults were detected and recovered
- Probes remained healthy throughout
- Regression tests passed post-chaos
- No data loss or SLA breach

### Degraded System (PARTIAL)

PARTIAL indicates:
- Some components were unavailable (preparing stage skipped them)
- Or regression tests couldn't run
- Review the preparing stage results to understand what was available

### Failed System (FAIL)

FAIL requires immediate investigation:
- Check which scenario(s) failed
- Review raw logs in `chaos_engineering/reports/`
- Check if probes detected faults
- Review regression failures

## Exporting Reports

### Markdown (default)

```bash
magenta chaos run --output report.md
magenta chaos run --output report.md --format markdown
```

### JSON

```bash
magenta chaos run --output report.json --format json
magenta chaos report --format json --output latest.json
```

### Without Recommendations

```bash
magenta chaos report --no-recommendations
```

## Integration with CI/CD

```yaml
# .github/workflows/chaos.yml
- name: Run Chaos Engineering
  run: |
    magenta chaos run --intensity 3 --output chaos-report.json --format json
    
- name: Upload Report
  uses: actions/upload-artifact@v4
  with:
    name: chaos-report
    path: chaos-report.json
```

## Frequency Recommendations

| Stage | Frequency | Intensity | Purpose |
|---|---|---|---|
| Development | Weekly | 1-2 | Catch regressions early |
| Pre-production | Before deploy | 3 | Validate deployment safety |
| Production | Monthly | 4-5 | Verify resilience at scale |
| Incident recovery | Post-incident | 2-3 | Verify fix effectiveness |

## Best Practices

1. **Start with `--dry-run`** to understand what will happen
2. **Use `--scenario`** to isolate specific faults
3. **Review preparing stage** to understand component availability
4. **Keep intensity low** (1-2) in development, higher (3-5) in staging
5. **Compare reports** across runs to track improvement
6. **Review raw logs** in `chaos_engineering/reports/` for detailed analysis
7. **Run regression** after any infrastructure change
