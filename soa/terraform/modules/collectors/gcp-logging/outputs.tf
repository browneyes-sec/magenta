# GCP Logging Module Outputs

output "pubsub_topic_id" {
  description = "Pub/Sub topic ID for log export"
  value       = google_pubsub_topic.logs_export.id
}

output "pubsub_subscription_id" {
  description = "Pub/Sub subscription ID for Magenta collector"
  value       = google_pubsub_subscription.magenta_collector.id
}

output "sink_name" {
  description = "Log router sink name"
  value       = google_logging_project_sink.to_pubsub.name
}

output "forwarder_job_name" {
  description = "Cloud Run job name (if enabled)"
  value       = try(google_cloud_run_v2_job.eventhub_forwarder[0].name, null)
}
