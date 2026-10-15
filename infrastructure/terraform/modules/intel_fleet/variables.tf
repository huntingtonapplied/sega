# intel_fleet — flat-network EC2 pool for the distributed swarm swarm.
# One subnet + self-referencing SG + cluster placement group so node<->node
# traffic (redis, ZMQ, EFS, consensus) is private-IP + low-latency = behaves
# like the local LAN. cloud-init makes each node swarm-ready + on the tailnet +
# EFS-mounted; sega's SwarmDeployer forms the swarm over SSH after apply.

variable "region" {
  type    = string
  default = "us-east-2"
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  type        = string
  description = "single subnet — all nodes land here (flat net)"
}

variable "availability_zone" {
  type        = string
  description = "must match the subnet's AZ (cluster PG is single-AZ)"
}

variable "worker_count" {
  type        = number
  default     = 3
  description = "worker nodes; 0 = single-node (head only) — cheapest provisioning smoke"
}

variable "head_type" {
  type    = string
  default = "m7i.2xlarge"
}

variable "worker_type" {
  type        = string
  default     = "m7i.8xlarge"
  description = "sim pool; r7i if RAM-bound, g6 for GPU train, t4g.small for cheap tests"
}

variable "cpu_arch" {
  type        = string
  default     = "x86_64"
  description = "x86_64 (m7i/c7i/t3) or arm64 (m7g/c7g/t4g — ~20% cheaper, matches M4-mini image builds)"
  validation {
    condition     = contains(["x86_64", "arm64"], var.cpu_arch)
    error_message = "cpu_arch must be x86_64 or arm64."
  }
}

variable "use_spot" {
  type        = bool
  default     = false
  description = "request spot instances (60-90% off; fine for sim pool + all testing)"
}

variable "ttl_minutes" {
  type        = number
  default     = 0
  description = "self-terminate backstop: if >0, each node terminates itself after N minutes (cloud-init `shutdown` + terminate-on-shutdown). Guards against forgotten teardown / a dead orchestrator. 0 = no auto-terminate (prod)."
}

variable "use_placement_group" {
  type        = bool
  default     = true
  description = "cluster placement group (low-latency). Turn OFF for t-series/cheap tests — burstable types don't support it."
}

variable "ssh_key_name" {
  type        = string
  default     = ""
  description = "EC2 key pair (optional — cloud-init uses tailscale SSH; leave empty to skip)"
}

variable "ssh_user" {
  type    = string
  default = "ubuntu"
}

variable "ts_authkey" {
  type        = string
  sensitive   = true
  description = "reusable/ephemeral tailscale pre-auth key"
}

variable "tailnet" {
  type    = string
  default = "tailnet-example.ts.net"
}

variable "drop_path" {
  type    = string
  default = "/opt/swarm/data"
}

variable "use_efs" {
  type        = bool
  default     = true
  description = "provision managed EFS as the cross-node shared store (needs elasticfilesystem:* on the deploy IAM user). false => each node uses a local dir at drop_path (no cross-node shared FS; fine for a plumbing smoke or where EFS isn't granted)."
}

variable "associate_public_ip" {
  type        = bool
  default     = false
  description = "give each node a public IP for outbound internet (cloud-init installs docker + tailscale). Set true on a public subnet with no NAT gateway; keep false for the prod private-subnet + NAT design. Inbound is locked by the SG either way."
}

variable "debug_ssh_key" {
  type        = string
  default     = ""
  description = "optional public SSH key added to the node's authorized_keys, for debugging cloud-init/bring-up over the public IP. Empty (default) adds none."
}

variable "root_volume_gb" {
  type    = number
  default = 100
}

variable "name_prefix" {
  type    = string
  default = "swarm-fleet"
}
