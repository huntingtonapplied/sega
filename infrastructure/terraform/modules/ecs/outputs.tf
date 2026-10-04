output "cluster_id" {
  description = "ID of the CS cluster"
  value       = aws_ecs_cluster.main.id
}

output "cluster_name" {
  description = "Name of the CS cluster"
  value       = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  description = "RN of the CS cluster"
  value       = aws_ecs_cluster.main.arn
}

output "task_execution_role_arn" {
  description = "RN of the CS task execution role"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "task_role_arn" {
  description = "RN of the CS task role"
  value       = aws_iam_role.ecs_task.arn
}

output "security_group_id" {
  description = "ID of the CS tasks security group"
  value       = aws_security_group.ecs_tasks.id
}

output "log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.ecs.name
}

output "load_balancer_arn" {
  description = "RN of the load balancer"
  value       = var.create_load_balancer ? aws_lb.main[].arn : null
}

output "load_balancer_dns_name" {
  description = "DNS name of the load balancer"
  value       = var.create_load_balancer ? aws_lb.main[].dns_name : null
}

output "load_balancer_zone_id" {
  description = "Hosted zone ID of the load balancer"
  value       = var.create_load_balancer ? aws_lb.main[].zone_id : null
}

output "target_group_arn" {
  description = "RN of the target group"
  value       = var.create_load_balancer ? aws_lb_target_group.main[].arn : null
}

output "alb_security_group_id" {
  description = "ID of the L security group"
  value       = var.create_load_balancer ? aws_security_group.alb[].id : null
}