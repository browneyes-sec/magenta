# 12 Canonical Operator Workflows

These are reusable Open WebUI prompts for common Magenta ASOAR operations.
Copy/paste into the Open WebUI chat to execute.

## 1. Incident Triage

```
Prompt: "Run triage on alert {alert_id} from {source}. 
Execute: triage_agent deploy
Action: collect_forensics on {target}
Reason: Initial triage — check scope and severity"
```

## 2. Threat Enrichment

```
Prompt: "Enrich indicators from alert {alert_id}.
Check Sentinel for related alerts in the last 24h.
Cross-reference with Entra for affected users.
Cross-reference with Defender for affected machines."
```

## 3. Host Containment

```
Execute: dictator deploy contain --model qwen2.5:7b
Action: isolate_host on {machine_id}
Reason: Confirmed malicious activity — immediate containment
```

## 4. Account Disablement

```
Execute: dictator deploy triage
Action: disable_account on {user_id}
Reason: Compromised credentials — disable pending investigation
```

## 5. Playbook Execution

```
Execute: automate run-playbook {playbook_name}
Trigger: {alert_id}
Description: Execute standard playbook for {incident_type}
```

## 6. Policy Override

```
prompt: dictator_override_teaming {mission_id} debate
Reason: Need adversarial analysis — switching to debate teaming
```

## 7. Approval Review

```
prompt: approval_card
Review all pending approvals and respond.
```

## 8. Mission Status

```
prompt: dictator_status
Summarize active missions and recent directives.
```

## 9. Artifact Generation

```
prompt: generate_artifact mission_throughput
Generate a mission throughput dashboard artifact.
```

## 10. Connector Health Check

```
prompt: connector_health
Check all integration connectors and report status.
```

## 11. Registry Search

```
prompt: registry_search {query}
Search for missions matching the given query.
```

## 12. Escalation

```
prompt: dictator_escalate {mission_id} Unable to resolve — requires human analysis
Reason: Automated triage exceeded escalation threshold
```
