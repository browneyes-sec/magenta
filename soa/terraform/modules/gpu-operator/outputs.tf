# GPU Operator Module Outputs

output "namespace" {
  description = "Namespace where GPU Operator is deployed"
  value       = var.enable_gpu_operator ? kubernetes_namespace.gpu_operator[0].metadata[0].name : null
}

output "runtime_class_name" {
  description = "RuntimeClass name for GPU workloads"
  value       = var.enable_gpu_operator ? kubernetes_runtime_class_v1.gpu[0].metadata[0].name : null
}

output "helm_release_status" {
  description = "Status of GPU Operator Helm release"
  value       = var.enable_gpu_operator ? helm_release.gpu_operator[0].status : null
}

output "monitoring_enabled" {
  description = "Whether GPU monitoring is enabled"
  value       = var.enable_monitoring
}

output "gfd_enabled" {
  description = "Whether GPU Feature Discovery is enabled"
  value       = var.enable_gfd
}
