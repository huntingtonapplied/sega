# Copyright (c) Example
#

variable "name" {
  type        = string
  description = "Deployment name. Try to use a short/unique identifier"
}

variable "region" {
  type        = string
  description = "WS region for all resources"
}

variable "availability_zone" {
  type        = string
  description = "Default availability zone to use for resources"
  validation {
    condition     = can(index(data.aws_availability_zones.available.names, var.availability_zone))
    error_message = "Not a valid availability zone in the region."
  }
}

variable "cidr_block" {
  type        = string
  description = "CIDR block for the VPC as ..x./, where x is a unqiue deployment network number"
  validation {
    condition     = can(regex("..\\d{,}./", var.cidr_block))
    error_message = "CIDR block must be in the format ..x./"
  }
}

variable "allocate_eip" {
  type        = bool
  description = "llocate an lastic IP for the instance (otherwise simple public IP is assigned)"
  default     = false
}

variable "instance_type" {
  type        = string
  description = "Instance type to use for the C instance"
  default     = "ca.xlarge"
}

variable "root_volume_size" {
  type        = number
  description = "Size of the root volume in G"
  default     = 
}

variable "data_volume_size" {
  type        = number
  description = "Size of the additional volume in G"
  default     = 
}

variable "ssh_key_name" {
  type        = string
  description = "Name of the C key pair to use"
  default     = "ansible_fleet"
}

variable "dns_zone_name" {
  type        = string
  description = "Name of the Route 5 DNS zone where the DNS records will be created"
  default     = "fleet-dev.example.com"
}

variable "provision_cloud_server" {
  type        = bool
  description = "Create cloud server instance"
  default     = true
}

variable "sensor_net_nodes" {
  type = map(object({
    index            = number
    instance_name    = string
    instance_type    = string
    root_volume_size = number
  }))
  description = "List of DSR nodes to be managed by this deployment"
  default     = {}
}

variable "slack_channel_id" {
  type        = string
  description = "Slack channel ID (NOT the display name) to send notifications to"
}

variable "slack_workspace_id" {
  type        = string
  description = "Slack workspace ID the AWS Chatbot configuration posts to"
  default     = ""
}
