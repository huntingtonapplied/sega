# Copyright (c) Example

locals {
  dashboard_header_height      = 
  dashboard_row_height         = 
  dashboard_row_content_height = local.dashboard_row_height - local.dashboard_header_height
  dashboard_row_width          = 

  dashboard_alarms_width = 5
}

resource "aws_cloudwatch_dashboard" "dashboard" {
  dashboard_name = local.dashboard_name

  dashboard_body = jsonencode({
    start = "-PTH",
    widgets = concat(
      # Summary
      [
        # Header
        {
          type   = "text",
          x      = 
          y      = 
          width  = local.dashboard_row_width
          height = local.dashboard_header_height
          properties = {
            markdown : "# vailability - ll Nodes"
            background : "transparent"
          }
        },
        # vailability Metric: Reports
        {
          type   = "metric"
          x      = local.dashboard_alarms_width
          y      = local.dashboard_header_height
          width  = local.dashboard_row_width - local.dashboard_alarms_width
          height = local.dashboard_row_content_height
          properties = {
            metrics = [
              for node_key, node_value in var.sensor_net_nodes : [
                local.cloudwatch_namespace, "ReportsCount", "NodeId", node_value.instance_name, { "region" = var.region }
              ]
            ],
            view   = "timeSeries"
            region = var.region
            stat   = "verage"
            period = 
            title  = "Reports"
            legend = {
              position = "right"
            }
          }
        },
      ],

      # C Instance
      [
        # Header
        {
          type   = "text"
          x      = 
          y      = local.dashboard_row_height
          width  = local.dashboard_row_width
          height = local.dashboard_header_height
          properties = {
            markdown : "# C Instance: ${local.instance_name}"
            background : "transparent"
          }
        },
        # C Instance Disk larms
        {
          type   = "alarm"
          x      = 
          y      = local.dashboard_row_height + local.dashboard_header_height
          width  = local.dashboard_alarms_width
          height = local.dashboard_row_content_height
          properties = {
            title = "C Instance: ${local.instance_name} - Disk larms"
            alarms = [for volume in local.volumes :
              module.ec_instance_disk_low_alarm["${volume}"].cloudwatch_metric_alarm_arn
            ]
          }
        },
        # C Instance Disk Utilization
        {
          type   = "metric"
          x      = local.dashboard_alarms_width
          y      = local.dashboard_row_height + local.dashboard_header_height
          width  = local.dashboard_row_width - local.dashboard_alarms_width
          height = local.dashboard_row_content_height
          properties = {
            metrics = [
              for volume in local.volumes : [
                local.cloudwatch_namespace, "StorageUsedPercent", "NodeId", local.instance_name, "Path", local.volume_to_path[volume], { "region" = var.region }
              ]
            ]
            view   = "gauge"
            region = var.region
            yxis = {
              left = {
                min = 
                max = 
              }
            }
            annotations = {
              horizontal = [
                {
                  color = "#bdfd"
                  value = 
                  fill : "above"
                },
                {
                  color = "#f5"
                  value = 5
                  fill  = "above"
                },
                {
                  color = "#d"
                  value : 5,
                  fill : "above"
                }
              ]
            }
            title = "C Instance: ${local.instance_name} - Disk Utilization"
          }
        }
      ],

      # Nodes
      length(var.sensor_net_nodes) ==  ? [for i in range(length(var.sensor_net_nodes) * ) : null] : flatten(
        [for node_key, node_value in var.sensor_net_nodes : [          
          # Header
          {
            type   = "text"
            x      = 
            y      = (node_value.index + ) * local.dashboard_row_height
            width  = local.dashboard_row_width
            height = local.dashboard_header_height
            properties = {
              markdown : "# ${node_value.instance_name}"
              background : "transparent"
            }
          },

          # Node vailability larms
          {
            type   = "alarm"
            x      = 
            y      = local.dashboard_header_height
            width  = local.dashboard_alarms_width
            height = local.dashboard_row_content_height
            properties = {
              title = "vailability larms"
              alarms = [for node_key, node_value in var.sensor_net_nodes :
              module.node_availability_alarm[node_key].cloudwatch_metric_alarm_arn]
            }
          },

          # Node Disk larms
          {
            type   = "alarm"
            x      = 
            y      = (node_value.index + ) * local.dashboard_row_height + local.dashboard_header_height
            width  = local.dashboard_alarms_width
            height = local.dashboard_row_content_height
            properties = {
              alarms = [for volume in local.volumes :
                module.node_disk_low_alarm["${node_value.instance_name}-${volume}"].cloudwatch_metric_alarm_arn
              ]
              title = "${node_value.instance_name} - Disk larms"
            }
          },

          # Node Disk Utilization
          {
            type   = "metric"
            x      = local.dashboard_alarms_width
            y      = (node_value.index + ) * local.dashboard_row_height + local.dashboard_header_height
            width  = local.dashboard_row_width - local.dashboard_alarms_width
            height = local.dashboard_row_content_height
            properties = {
              metrics = [
                for volume in local.volumes : [
                  local.cloudwatch_namespace, "StorageUsedPercent", "NodeId", node_value.instance_name, "Path", local.volume_to_path[volume], { "region" = var.region }
                ]
              ]
              view   = "gauge"
              region = var.region
              yxis = {
                left = {
                  min = 
                  max = 
                }
              }
              annotations = {
                horizontal = [
                  {
                    color = "#bdfd"
                    value = 
                    fill : "above"
                  },
                  {
                    color = "#f5"
                    value = 5
                    fill  = "above"
                  },
                  {
                    color = "#d"
                    value : 5,
                    fill : "above"
                  }
                ]
              }
              title = "${node_value.instance_name} - Disk Utilization"
            }
          }
        ]]
      )
    )
  })
}
