# Windows Admin Center (WAC) Deployment Runbook
## Alternative Windows log collection path (ADR-011 Tier 3 fallback)

Use this path when Azure Monitor Agent (AMA) cannot be deployed (no Azure Arc, air-gapped,
legacy OS < 2016, or policy restrictions). WAC provides HTTPS-based management and
scheduled PowerShell export for Event Log collection.

## Architecture

```
┌─────────────┐     HTTPS 443     ┌─────────────┐     WinRM-SSL 5986     ┌──────────────┐
│  Windows    │◄─────────────────►│   WAC       │◄──────────────────────►│  Collector   │
│  Server     │   (mgmt + export) │  Gateway    │   Get-WinEvent query   │  Service     │
└─────────────┘                   └─────────────┘                      └──────┬───────┘
                                                                            │
                                                                            ▼
                                                                      ┌──────────────┐
                                                                      │  Event Hubs  │
                                                                      │  raw-logs    │
                                                                      └──────────────┘
```

## Prerequisites

| Component | Requirement |
|---|---|
| WAC Gateway | Windows Server 2022/2019 Datacenter or Azure WAC (preview) |
| Target servers | Windows Server 2016+ with WinRM over HTTPS (5986) |
| Network | Collector → WAC (443), WAC → Target (5986); no direct Collector → Target |
| Certificates | WAC TLS cert (public CA), WinRM HTTPS listener cert (same CA) |
| Identity | gMSA or Entra ID hybrid for WAC auth; collector uses Entra ID MI |

## 1. WAC Gateway Deployment

### Azure Managed WAC (Recommended)

```bash
# Create WAC gateway in Azure
az extension add --name wac
az wac gateway create \
  --name "magenta-wac-${ENV}" \
  --resource-group "magenta-network" \
  --location eastus2 \
  --sku Standard \
  --public-network-access enabled

# Add target servers
az wac server add \
  --gateway-name "magenta-wac-${ENV}" \
  --resource-group "magenta-network" \
  --target-fqdn "win-prod-001.corp.example.com" \
  --credential-type "gMSA" \
  --gmsa-name "gmsa-wac-mgmt"
```

### Self-Hosted WAC (On-Prem)

```powershell
# On Windows Server 2022 Datacenter
Install-Module -Name Microsoft.Windows.AdminCenter -Repository PSGallery -Force
Install-WindowsAdminCenter -Port 443 -SslCertificateThumbprint <THUMBPRINT> -GenerateSslCertificate $false
```

## 2. WinRM over HTTPS Configuration (Target Servers)

### Option A: gMSA + HTTPS Listener (Recommended)

```powershell
# Run on each target server as Administrator
# 1. Create HTTPS listener with WAC gateway cert
$thumbprint = "ABC123..."  # Cert with CN=WAC Gateway FQDN, in LocalMachine\My
New-Item -Path WSMan:\LocalHost\Listener -Transport HTTPS -Address * -CertificateThumbprint $thumbprint -Force

# 2. Configure WinRM for gMSA auth
Set-Item WSMan:\localhost\Service\Auth\CredSSP -Value $true
Set-Item WSMan:\localhost\Service\AllowRemoteAccess -Value $true

# 3. Grant gMSA Read access to Event Logs
$gmsa = "CORP\gmsa-wac-mgmt$"
wevtutil sl Security /ca:"O:BAG:SYD:(A;;0x1;;;${gmsa})"
wevtutil sl System   /ca:"O:BAG:SYD:(A;;0x1;;;${gmsa})"
wevtutil sl Application /ca:"O:BAG:SYD:(A;;0x1;;;${gmsa})"
```

### Option B: Local Admin + Certificate Auth (Simpler, less secure)

```powershell
# 1. Enable WinRM HTTPS
winrm create winrm/config/Listener?Address=*+Transport=HTTPS @{Hostname="win-prod-001";CertificateThumbprint="ABC123..."}

# 2. Allow unencrypted for local testing ONLY (disable in prod)
winrm set winrm/config/service @{AllowUnencrypted="false"}
winrm set winrm/config/service/auth @{Certificate="true"}
```

## 3. Collector Configuration

Add to `soa/config/collectors.toml`:

```toml
[collector.windows-wac-corp]
type = "windows_event"
description = "Corporate Windows via WAC gateway"
enabled = true
poll_interval_seconds = 300
batch_size = 5000
options.host = "wac-gateway.corp.example.com"
options.winrm_port = 5986
options.username = "CORP\\gmsa-wac-mgmt$"  # gMSA, password managed by AD
options.transport = "ssl"
options.event_logs = ["Security", "System", "Application", "Microsoft-Windows-Sysmon/Operational"]
options.lookback_hours = 24
options.wac_gateway = true  # Flag for WAC path
```

## 4. PowerShell Collection Script (Deployed via WAC)

Save as `collect-winevents.ps1` on WAC gateway:

```powershell
param(
    [string]$TargetComputer,
    [string[]]$Logs = @("Security","System","Application"),
    [int]$HoursBack = 24,
    [string]$OutputPath
)

$since = (Get-Date).AddHours(-$HoursBack)
$events = @()

foreach ($log in $Logs) {
    try {
        $evts = Get-WinEvent -ComputerName $TargetComputer -LogName $log `
            -FilterXPath "*[System[TimeCreated[@SystemTime >= '${since:o}']]]" `
            -ErrorAction Stop
        $events += $evts | Select-Object @{N='LogName';E={$log}}, Id, LevelDisplayName, TimeCreated, Message, Properties
    } catch {
        Write-Error "Failed to query $log on $TargetComputer: $_"
    }
}

$events | ConvertTo-Json -Depth 5 | Out-File -FilePath $OutputPath -Encoding utf8
```

## 5. Collector Service Integration

The `WindowsEventCollector` class supports `wac_gateway: true` option:

```python
# magenta/integration/collectors/windows.py
if config.options.get("wac_gateway"):
    # Query WAC REST API instead of direct WinRM
    url = f"https://{config.options['host']}/api/v1/events/collect"
    # ... POST with target, logs, hours, get JSON back
```

## 6. Verification

```powershell
# Test WinRM connectivity from WAC
Test-WSMan -ComputerName win-prod-001 -Port 5986 -UseSSL -Authentication Certificate

# Test collection manually
.\collect-winevents.ps1 -TargetComputer win-prod-001 -Logs Security,System -HoursBack 1 -OutputPath test.json

# Check Event Hubs arrival
# KQL in Log Analytics (via Capture):
# raw_logs
# | where source_system == "windows_event"
# | where TimeGenerated > ago(10m)
```

## Troubleshooting

| Symptom | Resolution |
|---|---|
| WinRM 5986 timeout | Check NSG/firewall allows WAC subnet → target 5986; verify listener exists (`winrm enumerate winrm/config/Listener`) |
| Certificate auth failed | Cert must have EKU "Server Authentication" + CN matching FQDN; in LocalMachine\My |
| gMSA permission denied | Verify gMSA has "Read" on target log channels via `wevtutil gl <log>` |
| WAC gateway unreachable | Check WAC health at `https://<wac-fqdn>/health`; ensure public access or private endpoint |
| Events not in Event Hubs | Check collector logs; verify `raw-logs` topic exists; check idempotency key collision |

## Security Notes

- **No RDP for log collection** — RDP is break-glass only (per ADR-011)
- **TLS 1.2+ mandatory** — WinRM HTTP (5985) explicitly disabled
- **gMSA preferred** — No passwords in config; AD manages rotation
- **Network segmentation** — Collector zone DMZ; WAC in management subnet; targets in workload subnet
