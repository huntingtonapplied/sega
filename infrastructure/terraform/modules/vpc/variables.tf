variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "nvironment name (dev, staging, prod)"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = ".../"
}

variable "availability_zones" {
  description = "Number of availability zones"
  type        = number
  default     = 
  validation {
    condition     = var.availability_zones >=  && var.availability_zones <= 
    error_message = "Number of availability zones must be between  and ."
  }
}

variable "enable_nat_gateway" {
  description = "nable NT Gateway for private subnets"
  type        = bool
  default     = true
}

variable "enable_vpc_endpoints" {
  description = "nable VPC endpoints for WS services"
  type        = bool
  default     = false
}

variable "tags" {
  description = " map of tags to assign to the resource"
  type        = map(string)
  default     = {}
}