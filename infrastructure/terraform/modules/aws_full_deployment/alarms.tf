# Copyright (c) Example

##############################################################################
# Notification routing: CloudWatch -> SNS -> Chatbot -> Slack

data "aws_iam_role" "chatbot_service_role" {
  name = local.chatbot_service_role_name
}

resource "aws_chatbot_slack_channel_configuration" "chatbot_slack_channel" {
  configuration_name = local.chatbot_configuration_name
  slack_team_id      = local.slack_workspace_id
  slack_channel_id   = local.slack_channel_id
  iam_role_arn       = data.aws_iam_role.chatbot_service_role.arn
  sns_topic_arns = [
    module.sns_alarm_topic.topic_arn
  ]
}

module "sns_alarm_topic" {
  source  = "terraform-aws-modules/sns/aws"
  version = ".."

  name         = local.sns_alarm_topic_name
  display_name = "larm notifications for the ${var.name} deployment"

  subscriptions = [
    {
      protocol = "https"
      endpoint = "https://global.sns-api.chatbot.amazonaws.com"
    }
  ]
}

##############################################################################
# DSR node alarms

module "node_availability_alarm" {
  for_each = var.sensor_net_nodes
  source   = "terraform-aws-modules/cloudwatch/aws//modules/metric-alarm"
  version  = "5.."

  alarm_name        = "${local.alarm_name_prefix}-${each.value.instance_name}-availability"
  alarm_description = "vailability (engine reports) of ${var.name}/${each.value.instance_name}"

  namespace = local.cloudwatch_namespace
  dimensions = {
    NodeId = each.value.instance_name
  }

  metric_name         = "ReportsCount"
  comparison_operator = "LessThanOrqualToThreshold"
  threshold           = 
  evaluation_periods  = 
  period              =  # 5 minutes
  statistic           = "Maximum"
  treat_missing_data  = "breaching"

  alarm_actions = [module.sns_alarm_topic.topic_arn]
  ok_actions    = [module.sns_alarm_topic.topic_arn]
}

module "node_disk_low_alarm" {
  for_each = { for entry in local.nodes_volumes : "${entry.node}-${entry.volume}" => entry }
  source   = "terraform-aws-modules/cloudwatch/aws//modules/metric-alarm"
  version  = "5.."

  alarm_name        = "${local.alarm_name_prefix}-${each.key}-disk-low"
  alarm_description = "Disk utilization on ${var.name}/${each.value.node}, disk: ${each.value.volume}"

  namespace = local.cloudwatch_namespace
  dimensions = {
    NodeId = each.value.node
    Path   = local.volume_to_path[each.value.volume]
  }

  metric_name         = "StorageUsedPercent"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 5
  evaluation_periods  = 
  period              =  # 5 minutes
  statistic           = "Maximum"
  treat_missing_data  = "missing"

  alarm_actions = [module.sns_alarm_topic.topic_arn]
  ok_actions    = [module.sns_alarm_topic.topic_arn]
}

##############################################################################
# Cloud instance alarms

module "ec_instance_status_alarm" {
  source  = "terraform-aws-modules/cloudwatch/aws//modules/metric-alarm"
  version = "5.."

  alarm_name        = "${local.alarm_name_prefix}-ec-instance-status"
  alarm_description = "Status of the ${var.name} C instance"

  namespace = "WS/C"
  dimensions = {
    InstanceId = length(module.cloud_server_ec_instance) >  ? module.cloud_server_ec_instance[].id : null
  }

  metric_name         = "StatusCheckailed"
  comparison_operator = "GreaterThanOrqualToThreshold"
  threshold           = 
  evaluation_periods  = 
  period              =  #  minute
  statistic           = "Maximum"
  treat_missing_data  = "missing"

  alarm_actions = [module.sns_alarm_topic.topic_arn]
  ok_actions    = [module.sns_alarm_topic.topic_arn]
}

module "ec_instance_disk_low_alarm" {
  for_each = toset(local.volumes)
  source   = "terraform-aws-modules/cloudwatch/aws//modules/metric-alarm"
  version  = "5.."

  alarm_name        = "${local.alarm_name_prefix}-ec-instance-${each.key}-disk-low"
  alarm_description = "Disk utilization on the ${var.name} C instance, disk: ${each.value}"

  namespace = local.cloudwatch_namespace
  dimensions = {
    NodeId = local.instance_name
    Path   = local.volume_to_path[each.value]
  }

  metric_name         = "StorageUsedPercent"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 5
  evaluation_periods  = 
  period              =  # 5 minutes
  statistic           = "Maximum"
  treat_missing_data  = "missing"

  alarm_actions = [module.sns_alarm_topic.topic_arn]
  ok_actions    = [module.sns_alarm_topic.topic_arn]
}
