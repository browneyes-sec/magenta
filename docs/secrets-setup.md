# GitHub Secrets Setup Guide for Staging

This guide explains how to configure the required GitHub secrets for the staging deployment pipeline.

## Required Secrets

### Azure Credentials (for Terraform)

| Secret | Description | How to obtain |
|--------|-------------|---------------|
| `AZURE_CLIENT_ID` | Azure service principal app/client ID | Azure Portal > App Registrations > Your app > Overview |
| `AZURE_CLIENT_SECRET` | Azure service principal secret | Azure Portal > App Registrations > Your app > Certificates & secrets |
| `AZURE_TENANT_ID` | Azure AD tenant ID | Azure Portal > Azure Active Directory > Overview |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID | Azure Portal > Subscriptions > Your subscription |

### Kubernetes (for Kustomize deploy)

| Secret | Description | How to obtain |
|--------|-------------|---------------|
| `KUBECONFIG_STAGING` | Kubeconfig for staging AKS cluster | `az aks get-credentials --resource-group <rg> --name <cluster>` |

### Application Secrets

| Secret | Description | How to set |
|--------|-------------|------------|
| `MAGENTA_API_KEY` | API key for workflow engine auth | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

## Setup via GitHub CLI

```bash
# Set Azure credentials
gh secret set AZURE_CLIENT_ID --body "<your-client-id>"
gh secret set AZURE_CLIENT_SECRET --body "<your-client-secret>"
gh secret set AZURE_TENANT_ID --body "<your-tenant-id>"
gh secret set AZURE_SUBSCRIPTION_ID --body "<your-subscription-id>"

# Set Kubeconfig (pipe from file or command)
az aks get-credentials --resource-group magenta-staging-rg --name magenta-staging-aks --file staging.kubeconfig
gh secret set KUBECONFIG_STAGING --body-file staging.kubeconfig

# Set API key
MAGENTA_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
gh secret set MAGENTA_API_KEY --body "$MAGENTA_API_KEY"
```

## K8s Secret (Post-Deploy)

After Terraform creates the cluster, create the application secret:

```bash
kubectl create secret generic magenta-secrets \
  --from-literal=api-key="$MAGENTA_API_KEY" \
  -n magenta-staging
```

## Environment Protection Rules

Configure the `staging` environment in GitHub:
1. Go to **Settings > Environments > staging**
2. Enable **Required reviewers** (optional)
3. Enable **Wait timer** (optional, 5 min recommended)
4. Restrict to `main` and `staging` branches

## Verification

After setup, trigger a deploy:

```bash
# Push to staging to trigger deploy-staging.yml
git push origin staging

# Monitor the deploy
gh run list --repo browneyes-sec/magenta --branch staging --limit 3
```

Once deployed, run smoke tests:

```bash
python scripts/smoke_test_staging.py \
  --url "http://<staging-api-ip>:8000" \
  --api-key "$MAGENTA_API_KEY"
```
