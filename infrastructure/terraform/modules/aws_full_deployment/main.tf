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

  provision_cloud_server      = var.provision_cloud_server
  instance_name               = var.name
  root_volume_name            = "${var.name}-root"
  data_volume_name            = "${var.name}-data"
  instance_backup_policy_name = "${local.instance_name}-backup"
  instance_role_name          = "${var.name}-instance-role"
  dlm_service_role_name       = "WSDataLifecycleManagerDefaultRole" # global resource (needs to exist in the account)

  s_bucket_name             = "example-sensor-net-${var.name}"
  s_full_access_policy_name = "${var.name}-s-full-access-policy"

  cloudwatch_namespace       = "Example/DSR/${var.name}"
  alarm_name_prefix          = var.name
  sns_alarm_topic_name       = "${var.name}-alarm-topic"
  chatbot_configuration_name = "${var.name}-slack"
  chatbot_service_role_name  = "WSChatbot-role" # global resource (needs to exist in the account)
  slack_workspace_id         = var.slack_workspace_id
  slack_channel_id           = var.slack_channel_id

  dashboard_name = "${var.name}-dashboard"
  # Cloudwatch metrics logic
  volumes = ["root", "data"]
  volume_to_path = {
    root = "/",
    data = "/data"
  }
  nodes_volumes = distinct(flatten([
    for node_key, node_value in var.sensor_net_nodes : [
      for volume in local.volumes : {
        node   = node_value.instance_name
        volume = volume
      }
    ]
  ]))
}
