# Root Module Variables — Magenta Multi-Cloud Terraform

variable "environment" {
  description = "Deployment environment"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "resource_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "magenta"
}

variable "common_tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default = {
    project     = "magenta"
    component   = "asoar"
    managed-by  = "terraform"
    cost-center = "security-operations"
  }
}

# ── Provider Feature Flags ───────────────────────────────────────────────

variable "enable_azure" {
  description = "Enable Azure provider"
  type        = bool
  default     = true
}

variable "enable_aws" {
  description = "Enable AWS provider"
  type        = bool
  default     = false
}

variable "enable_gcp" {
  description = "Enable GCP provider"
  type        = bool
  default     = false
}

variable "enable_vsphere" {
  description = "Enable vSphere (private cloud) provider"
  type        = bool
  default     = false
}

variable "enable_kubernetes" {
  description = "Provision managed Kubernetes clusters"
  type        = bool
  default     = true
}

variable "enable_network_hub" {
  description = "Provision multi-cloud hub network"
  type        = bool
  default     = false
}

variable "use_new_k8s_modules" {
  description = "Use new per-provider K8s modules instead of generic compute module"
  type        = bool
  default     = false
}

# ── Azure ────────────────────────────────────────────────────────────────

variable "azure_subscription_id" {
  description = "Azure subscription ID"
  type        = string
  sensitive   = true
}

variable "azure_location" {
  description = "Azure region"
  type        = string
  default     = "eastus2"
}

variable "azure_log_analytics_workspace_id" {
  description = "Azure Log Analytics workspace ID for monitoring"
  type        = string
  default     = null
}

# ── AWS ──────────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_role_arn" {
  description = "AWS IAM role ARN for Terraform"
  type        = string
  default     = ""
}

# ── GCP ──────────────────────────────────────────────────────────────────

variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
  default     = ""
}

variable "gcp_region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "gcp_impersonate_sa" {
  description = "GCP service account for impersonation"
  type        = string
  default     = ""
}

# ── vSphere ──────────────────────────────────────────────────────────────

variable "vsphere_user" {
  description = "vSphere username"
  type        = string
  default     = ""
}

variable "vsphere_password" {
  description = "vSphere password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "vsphere_server" {
  description = "vSphere server FQDN"
  type        = string
  default     = ""
}

# ── Compute ──────────────────────────────────────────────────────────────

variable "compute_vm_sku" {
  description = "VM SKU for compute nodes (generic module)"
  type        = string
  default     = "Standard_D4s_v5"
}

variable "compute_node_count" {
  description = "Number of compute nodes per provider (generic module)"
  type        = number
  default     = 3
}

# ── Kubernetes ───────────────────────────────────────────────────────────

variable "k8s_node_pool_sku" {
  description = "Node pool VM SKU for Kubernetes (generic module)"
  type        = string
  default     = "Standard_D4s_v5"
}

variable "k8s_node_count" {
  description = "Number of K8s nodes per cluster (generic module)"
  type        = number
  default     = 3
}

variable "k8s_service_cidr" {
  description = "Service CIDR for Kubernetes"
  type        = string
  default     = "10.96.0.0/12"
}

variable "k8s_kubernetes_version" {
  description = "Kubernetes version for new modules"
  type        = string
  default     = "1.31"
}

variable "k8s_system_node_sku" {
  description = "System node pool VM SKU (new modules)"
  type        = string
  default     = "Standard_D4s_v5"
}

variable "k8s_system_node_count" {
  description = "System node pool count (new modules)"
  type        = number
  default     = 2
}

variable "k8s_user_node_pools" {
  description = "User node pool definitions (new modules)"
  type = map(object({
    vm_size    = string
    node_count = optional(number, 2)
    node_labels = optional(map(string), {})
    node_taints = optional(list(string), [])
  }))
  default = {}
}

variable "k8s_private_cluster" {
  description = "Deploy private K8s clusters"
  type        = bool
  default     = false
}

variable "k8s_enable_auto_scaling" {
  description = "Enable cluster autoscaler"
  type        = bool
  default     = true
}

variable "k8s_min_node_count" {
  description = "Minimum node count (autoscaler)"
  type        = number
  default     = 1
}

variable "k8s_max_node_count" {
  description = "Maximum node count (autoscaler)"
  type        = number
  default     = 6
}

# ── Network ──────────────────────────────────────────────────────────────

variable "azure_hub_cidr" {
  description = "Azure hub VNet CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "azure_hub_subnets" {
  description = "Azure hub subnet definitions"
  type        = map(string)
  default = {
    gateway  = "10.0.1.0/24"
    firewall = "10.0.2.0/24"
    shared   = "10.0.3.0/24"
  }
}

variable "aws_hub_cidr" {
  description = "AWS hub VPC CIDR"
  type        = string
  default     = "10.1.0.0/16"
}

variable "gcp_hub_cidr" {
  description = "GCP hub subnet CIDR"
  type        = string
  default     = "10.2.0.0/16"
}

# ── vSphere Specific ─────────────────────────────────────────────────────

variable "vsphere_datacenter" {
  description = "vSphere datacenter"
  type        = string
  default     = "dc-01"
}

variable "vsphere_compute_cluster" {
  description = "vSphere compute cluster"
  type        = string
  default     = "cluster-01"
}

variable "vsphere_datastore" {
  description = "vSphere datastore"
  type        = string
  default     = "datastore-01"
}

variable "vsphere_network" {
  description = "vSphere port group"
  type        = string
  default     = "VM Network"
}

variable "vsphere_template" {
  description = "vSphere VM template"
  type        = string
  default     = "ubuntu-24-04-template"
}

variable "vsphere_vm_folder" {
  description = "vSphere VM folder"
  type        = string
  default     = "/magenta"
}

variable "vsphere_cp_cidr" {
  description = "vSphere control plane CIDR"
  type        = string
  default     = "192.168.10.0/24"
}

variable "vsphere_worker_cidr" {
  description = "vSphere worker CIDR"
  type        = string
  default     = "192.168.11.0/24"
}

# ── Capture / Event Hubs ─────────────────────────────────────────────────

variable "enable_capture" {
  description = "Enable Event Hubs Capture → ADLS Gen2 module"
  type        = bool
  default     = false
}

variable "capture_topics" {
  description = "Event Hubs topics with Capture enabled"
  type        = list(string)
  default     = ["raw-logs", "raw-alerts", "enriched-alerts", "enriched-events", "audit", "dead-letter"]
}

variable "capture_topic_partitions" {
  description = "Partition count per capture topic"
  type        = map(number)
  default = {
    "raw-logs"        = 16
    "raw-alerts"      = 8
    "enriched-alerts" = 8
    "enriched-events" = 8
    "audit"           = 4
    "dead-letter"     = 1
  }
}

variable "capture_topic_retention_days" {
  description = "Message retention in days per capture topic"
  type        = map(number)
  default = {
    "raw-logs"        = 7
    "raw-alerts"      = 7
    "enriched-alerts" = 1
    "enriched-events" = 1
    "audit"           = 7
    "dead-letter"     = 2
  }
}

variable "capture_eventhub_sku" {
  description = "Event Hubs SKU for capture namespace"
  type        = string
  default     = "Standard"
}

variable "capture_eventhub_capacity" {
  description = "Event Hubs throughput units"
  type        = number
  default     = 2
}

variable "capture_consumer_groups" {
  description = "Consumer groups per capture topic"
  type        = list(string)
  default     = ["$Default", "normalizer", "log-normalizer", "vectorizer-logs", "orchestrator", "registry", "dlq-debug"]
}

# ── Collector Feature Flags ────────────────────────────────────────────────

variable "enable_azure_dcr" {
  description = "Enable Azure Data Collection Rule module"
  type        = bool
  default     = false
}

variable "enable_aws_cloudtrail" {
  description = "Enable AWS CloudTrail → S3 + EventBridge module"
  type        = bool
  default     = false
}

variable "enable_aws_eventhub_partner" {
  description = "Enable AWS EventBridge → partner Event Hub forwarding"
  type        = bool
  default     = false
}

variable "aws_kms_key_id" {
  description = "KMS key ID for CloudTrail encryption"
  type        = string
  default     = ""
}

variable "aws_partner_eventhub_arn" {
  description = "Partner Event Hub ARN (Azure Event Hubs partner integration)"
  type        = string
  default     = ""
}

variable "aws_collector_role_arn" {
  description = "IAM role ARN for Magenta collector (cross-account S3 read)"
  type        = string
  default     = ""
}

variable "enable_gcp_logging" {
  description = "Enable GCP Cloud Logging → Pub/Sub module"
  type        = bool
  default     = false
}

variable "enable_gcp_eventhub_forwarder" {
  description = "Enable GCP Cloud Run forwarder to Event Hubs"
  type        = bool
  default     = false
}

variable "gcp_forwarder_image" {
  description = "Container image for GCP Event Hubs forwarder"
  type        = string
  default     = "magenta/eventhub-forwarder:latest"
}

variable "gcp_forwarder_service_account" {
  description = "GCP service account for forwarder job"
  type        = string
  default     = ""
}

variable "gcp_collector_service_account" {
  description = "GCP service account for Magenta collector Pub/Sub subscriber"
  type        = string
  default     = ""
}

variable "azure_key_vault_ids" {
  description = "Key Vault resource IDs for DCR diagnostic settings"
  type        = list(string)
  default     = []
}

variable "enable_ingest_gateway" {
  description = "Enable Ingest Gateway (Application Gateway + WAF + mTLS)"
  type        = bool
  default     = false
}

variable "ingest_gateway_capacity" {
  description = "WAF v2 capacity units"
  type        = number
  default     = 2
}

variable "gateway_subnet_id" {
  description = "Subnet ID for Application Gateway (if not using network hub)"
  type        = string
  default     = ""
}

variable "ingest_api_fqdns" {
  description = "FQDNs of ingest API backend instances"
  type        = list(string)
  default     = []
}

variable "dns_zone_name" {
  description = "Public DNS zone name (e.g., magenta.example.com)"
  type        = string
  default     = ""
}

variable "dns_zone_resource_group" {
  description = "Resource group containing DNS zone"
  type        = string
  default     = ""
}

variable "ingest_gateway_ssl_cert_data" {
  description = "Base64-encoded PFX certificate for ingest gateway"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ingest_gateway_ssl_cert_password" {
  description = "PFX password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ingest_gateway_client_ca_data" {
  description = "Base64-encoded CA certificate for mTLS client verification"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ingest_gateway_client_ca_issuer_dn" {
  description = "Expected issuer DN for client certificates"
  type        = string
  default     = ""
}

# ── Budget ────────────────────────────────────────────────────────────────

variable "budget_monthly_total" {
  description = "Total monthly budget across all providers (USD)"
  type        = number
  default     = 3000
}

variable "budget_provider_amounts" {
  description = "Per-provider monthly budgets (USD)"
  type        = map(number)
  default = {
    azure = 1500
    aws   = 500
  }
}

variable "budget_notification_email" {
  description = "Email for budget alerts"
  type        = string
  default     = "finops@magenta.local"
}

variable "budget_webhook_url" {
  description = "Webhook URL for budget alerts"
  type        = string
  default     = ""
}

variable "budget_alert_thresholds" {
  description = "Budget alert thresholds (percentage)"
  type        = list(number)
  default     = [50, 80, 95]
}

variable "budget_filter_tags" {
  description = "Tags for budget scope filtering"
  type        = map(list(string))
  default = {
    project     = ["magenta"]
    environment = ["dev", "staging", "production"]
  }
}
