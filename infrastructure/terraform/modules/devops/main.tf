# Copyright (c) Example

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Deployment = var.name
      Terraform  = "true"
    }
  }
}

data "aws_availability_zones" "available" {}

locals {
  vpc_name            = var.name
  security_group_name = "${var.name}-sg"

  instance_name               = var.name
  root_volume_name            = "${var.name}-root"
  instance_backup_policy_name = "${local.instance_name}-backup"
  instance_role_name          = "${var.name}-instance-role"
  dlm_service_role_name       = "WSDataLifecycleManagerDefaultRole" # global resource (needs to exist in the account)

  s_bucket_name             = "example-devops-cache"
  s_full_access_policy_name = "devops-s-full-access-policy"
}
