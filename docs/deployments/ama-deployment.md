# Azure Monitor Agent (AMA) Deployment Runbook
## Preferred Windows endpoint log collection path (ADR-011 Tier 3)

This runbook covers deploying AMA to Windows servers for collecting Event Log
and forwarding to Log Analytics, where Diagnostic Settings stream to Event Hubs.

## Prerequisites

- Windows Server 2016+ or Azure Arc-enabled servers
- Azure Managed Identity (system-assigned preferred)
- Network: outbound HTTPS to `*.ods.opinsights.azure.com` and `*.oms.opinsights.azure.com`

## Deployment via Azure Policy (Recommended)

```bash
# 1. Assign built-in policy
az policy assignment create \
  --name "deploy-ama-windows" \
  --policy "e71cabf5-4841-4f27-a2c4-4a7c2ac0c7f2" \
  --assign-identity \
  --location eastus2

# 2. Create Data Collection Rule (DCR) — see Terraform module:
#    soa/terraform/modules/collectors/azure-dcr/main.tf

# 3. Create Data Collection Association (DCA)
az monitor data-collection rule association create \
  --name "magenta-windows-events" \
  --rule-id "/subscriptions/.../dataCollectionRules/magenta-staging-dcr" \
  --resource "/subscriptions/.../virtualMachines/.../providers/Microsoft.Compute/virtualMachines/vm-win-001"
```

## Manual Deployment (Arc-Enabled Server)

```powershell
# 1. Install AMA extension via Arc
az connectedmachine extension create \
  --machine-name "vm-win-001" \
  --name "AzureMonitorWindowsAgent" \
  --publisher "Microsoft.Azure.Monitor" \
  --type "AzureMonitorWindowsAgent" \
  --resource-group "magenta-compute"

# 2. Associate DCR
az monitor data-collection rule association create \
  --name "magenta-windows-events" \
  --rule-id "<dcr-id>" \
  --resource "<arc-machine-id>"
```

## Event Log Configuration (DCR)

Configure DCR to collect these Windows Event Log channels:

| Log | Channels | Event IDs |
|---|---|---|
| Security | Critical, Error, Warning, Audit Success, Audit Failure | All (default) |
| System | Critical, Error, Warning | All |
| Application | Critical, Error, Warning | All |
| Windows Defender | Warning, Error | 1116, 1117, 1118 |
| PowerShell Operational | Warning, Error | 4103, 4104, 4105 |

## Verification

```kql
// Check data flow in Log Analytics
SecurityEvent
| where TimeGenerated > ago(5m)
| summarize count() by Computer
| order by count_ desc

Heartbeat
| where TimeGenerated > ago(5m) and Category == "Azure Monitor Agent"
| project Computer, TimeGenerated, Version
```

## Troubleshooting

| Symptom | Check |
|---|---|
| No events in LA | Verify AMA extension status on VM; check `C:\Resources\AMAData\` logs |
| DCR not applying | Run `Get-SrvMgmtDataCollectionRule` PowerShell cmdlet |
| Network blocked | Test connectivity: `Test-NetConnection -ComputerName <ods-endpoint> -Port 443` |
| Identity missing | Confirm system-assigned MI is enabled: `az vm identity show --name <vm>` |
