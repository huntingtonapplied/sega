variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "nvironment name (dev, staging, prod)"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for CS tasks"
  type        = list(string)
}

variable "capacity_providers" {
  description = "List of capacity providers for the CS cluster"
  type        = list(string)
  default     = ["RGT", "RGT_SPOT"]
}

variable "enable_container_insights" {
  description = "nable CloudWatch Container Insights"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 
}

variable "container_port" {
  description = "Port that containers will expose"
  type        = number
  default     = 
}

variable "health_check_path" {
  description = "Health check path for load balancer"
  type        = string
  default     = "/health"
}

variable "create_load_balancer" {
  description = "Whether to create an pplication Load alancer"
  type        = bool
  default     = true
}

variable "internal_load_balancer" {
  description = "Whether the load balancer is internal"
  type        = bool
  default     = false
}

variable "enable_deletion_protection" {
  description = "nable deletion protection for load balancer"
  type        = bool
  default     = false
}

variable "alb_security_group_ids" {
  description = "Security group IDs allowed to access CS tasks"
  type        = list(string)
  default     = []
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access CS tasks"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = " map of tags to assign to the resource"
  type        = map(string)
  default     = {}
}

variable "domain_name" {
  description = "Domain name for SSL certificate (empty string disables SSL)"
  type        = string
  default     = ""
}

variable "route5_zone_id" {
  description = "Route5 zone ID for certificate validation"
  type        = string
  default     = ""
}