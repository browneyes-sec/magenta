# GCP Cloud Logging → Event Hubs Module
# Creates Pub/Sub topic + subscription for log export,
# and optional Cloud Run job to forward to Event Hubs.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# ── Pub/Sub Topic for Log Export ─────────────────────────────────────────

resource "google_pubsub_topic" "logs_export" {
  name = "${var.resource_prefix}-${var.environment}-logs-export"
  labels = var.common_tags
}

# ── Pub/Sub Subscription for Magenta Collector ───────────────────────────

resource "google_pubsub_subscription" "magenta_collector" {
  name  = "${var.resource_prefix}-${var.environment}-magenta-collector"
  topic = google_pubsub_topic.logs_export.id
  ack_deadline_seconds = 600
  message_retention_duration = "86400s"
  retain_acked_messages = true
  expiration_policy {
    ttl = "2592000s"
  }
  labels = var.common_tags
}

# ── Log Router Sink → Pub/Sub ────────────────────────────────────────────

resource "google_logging_project_sink" "to_pubsub" {
  name        = "${var.resource_prefix}-${var.environment}-to-pubsub"
  destination = "pubsub.googleapis.com/${google_pubsub_topic.logs_export.id}"
  filter = <<-EOT
    resource.type="k8s_container" OR
    resource.type="gce_instance" OR
    resource.type="cloud_run_revision" OR
    resource.type="audited_resource" OR
    protoPayload.authenticationInfo.principalEmail=~".*"
  EOT
  include_children = false
  bigquery_options {
    use_partitioned_tables = true
  }
}

# ── IAM for Sink Writer ──────────────────────────────────────────────────

resource "google_project_iam_member" "sink_writer" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_logging_project_sink.to_pubsub.writer_identity}"
}

# ── Cloud Run Job to Forward to Event Hubs (optional) ────────────────────

resource "google_cloud_run_v2_job" "eventhub_forwarder" {
  count = var.enable_eventhub_forwarder ? 1 : 0
  name  = "${var.resource_prefix}-${var.environment}-eventhub-forwarder"
  location = var.region
  template {
    template {
      containers {
        image = var.forwarder_image
        env {
          name  = "EVENTHUB_NAMESPACE"
          value = var.eventhub_namespace
        }
        env {
          name  = "EVENTHUB_TOPIC"
          value = var.eventhub_topic
        }
        env {
          name  = "PUBSUB_SUBSCRIPTION"
          value = google_pubsub_subscription.magenta_collector.id
        }
      }
      service_account = var.forwarder_service_account
    }
    scaling {
      min_instance_count = 1
      max_instance_count = 3
    }
  }
}

# ── Service Account for Forwarder ────────────────────────────────────────

resource "google_service_account" "forwarder" {
  count  = var.enable_eventhub_forwarder ? 1 : 0
  account_id   = "${var.resource_prefix}-${var.environment}-eventhub-forwarder"
  display_name = "Event Hubs Log Forwarder"
}

# ── IAM for Subscriber (Magenta Collector) ──────────────────────────────

resource "google_project_iam_member" "subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${var.collector_service_account}"
}
