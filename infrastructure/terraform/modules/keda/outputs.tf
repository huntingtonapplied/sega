# KEDA Module Outputs

output "keda_namespace" {
  description = "Namespace where KEDA is installed"
  value       = var.namespace
}

output "keda_version" {
  description = "Installed KEDA version"
  value       = var.keda_version
}

output "simulations_namespace" {
  description = "Namespace for simulation workloads"
  value       = var.simulations_namespace
}

output "redis_auth_name" {
  description = "Name of Redis TriggerAuthentication resource"
  value       = var.create_redis_secret ? "redis-auth" : null
}
