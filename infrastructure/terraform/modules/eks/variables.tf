# EKS Module Variables
#
# Architecture Reference:
#   /docs/architecture/orchestration/KUBERNETES_AUTOSCALING_ARCHITECTURE.md

# Cluster Configuration
variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "example-simulations"
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.28"
}

variable "aws_region" {
  description = "AWS region for the cluster"
  type        = string
}

# Network Configuration
variable "vpc_id" {
  description = "VPC ID where the cluster will be deployed"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for the cluster"
  type        = list(string)
}

variable "cluster_endpoint_public_access" {
  description = "Enable public access to the cluster endpoint"
  type        = bool
  default     = true
}

# General Node Group
variable "general_instance_types" {
  description = "Instance types for general purpose nodes"
  type        = list(string)
  default     = ["m5.large"]
}

variable "general_min_size" {
  description = "Minimum number of general nodes"
  type        = number
  default     = 2
}

variable "general_max_size" {
  description = "Maximum number of general nodes"
  type        = number
  default     = 10
}

variable "general_desired_size" {
  description = "Desired number of general nodes"
  type        = number
  default     = 2
}

# GPU Node Group (for simulation engines)
variable "gpu_instance_types" {
  description = "Instance types for GPU nodes (simulation engines)"
  type        = list(string)
  default     = ["g4dn.xlarge"]
}

variable "gpu_min_size" {
  description = "Minimum number of GPU nodes (0 for scale-to-zero)"
  type        = number
  default     = 0
}

variable "gpu_max_size" {
  description = "Maximum number of GPU nodes"
  type        = number
  default     = 20
}

variable "gpu_desired_size" {
  description = "Desired number of GPU nodes"
  type        = number
  default     = 0
}

# Cluster Autoscaler
variable "enable_cluster_autoscaler" {
  description = "Enable Cluster Autoscaler for automatic node scaling"
  type        = bool
  default     = true
}

variable "cluster_autoscaler_version" {
  description = "Cluster Autoscaler Helm chart version"
  type        = string
  default     = "9.29.0"
}

variable "scale_down_unneeded_time" {
  description = "Time before unneeded nodes are scaled down"
  type        = string
  default     = "10m"
}

variable "scale_down_delay_after_add" {
  description = "Delay before scaling down after adding a node"
  type        = string
  default     = "10m"
}

# NVIDIA Device Plugin
variable "enable_nvidia_device_plugin" {
  description = "Enable NVIDIA Device Plugin for GPU support"
  type        = bool
  default     = true
}

variable "nvidia_device_plugin_version" {
  description = "NVIDIA Device Plugin Helm chart version"
  type        = string
  default     = "0.14.0"
}

# Tags
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
