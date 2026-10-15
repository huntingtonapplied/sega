# KEDA Module Variables
#
# Architecture Reference:
#   /docs/architecture/orchestration/KUBERNETES_AUTOSCALING_ARCHITECTURE.md

# KEDA Configuration
variable "keda_version" {
  description = "KEDA Helm chart version"
  type        = string
  default     = "2.12.0"
}

variable "namespace" {
  description = "Namespace for KEDA operator"
  type        = string
  default     = "keda"
}

# Resource limits for KEDA operator
variable "operator_cpu_limit" {
  description = "CPU limit for KEDA operator"
  type        = string
  default     = "1"
}

variable "operator_memory_limit" {
  description = "Memory limit for KEDA operator"
  type        = string
  default     = "1000Mi"
}

variable "operator_cpu_request" {
  description = "CPU request for KEDA operator"
  type        = string
  default     = "100m"
}

variable "operator_memory_request" {
  description = "Memory request for KEDA operator"
  type        = string
  default     = "100Mi"
}

# Prometheus integration
variable "enable_prometheus_metrics" {
  description = "Enable Prometheus metrics server"
  type        = bool
  default     = true
}

variable "enable_prometheus_operator" {
  description = "Enable Prometheus operator integration"
  type        = bool
  default     = false
}

# Redis configuration
variable "create_redis_secret" {
  description = "Create Redis credentials secret"
  type        = bool
  default     = true
}

variable "redis_url" {
  description = "Redis URL for queue monitoring"
  type        = string
  default     = "redis.simulations.svc.cluster.local:6379"
}

variable "redis_password" {
  description = "Redis password"
  type        = string
  sensitive   = true
  default     = ""
}

# Simulations namespace
variable "simulations_namespace" {
  description = "Namespace for simulation workloads"
  type        = string
  default     = "simulations"
}

variable "create_simulations_namespace" {
  description = "Create simulations namespace"
  type        = bool
  default     = true
}
