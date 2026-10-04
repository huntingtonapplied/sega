output "db_instance_id" {
  description = "RDS instance ID"
  value       = aws_db_instance.main.id
}

output "db_instance_arn" {
  description = "RDS instance RN"
  value       = aws_db_instance.main.arn
}

output "db_instance_address" {
  description = "RDS instance hostname"
  value       = aws_db_instance.main.address
}

output "db_instance_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.main.endpoint
}

output "db_instance_port" {
  description = "RDS instance port"
  value       = aws_db_instance.main.port
}

output "db_instance_name" {
  description = "RDS instance database name"
  value       = aws_db_instance.main.db_name
}

output "db_instance_username" {
  description = "RDS instance master username"
  value       = aws_db_instance.main.username
  sensitive   = true
}

output "db_subnet_group_id" {
  description = "D subnet group ID"
  value       = aws_db_subnet_group.main.id
}

output "db_parameter_group_id" {
  description = "D parameter group ID"
  value       = aws_db_parameter_group.main.id
}

output "db_option_group_id" {
  description = "D option group ID"
  value       = var.create_option_group ? aws_db_option_group.main[].id : null
}

output "security_group_id" {
  description = "RDS security group ID"
  value       = aws_security_group.rds.id
}

output "secrets_manager_secret_arn" {
  description = "RN of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_password.arn
}

output "secrets_manager_secret_name" {
  description = "Name of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_password.name
}

output "read_replica_id" {
  description = "ID of the read replica"
  value       = var.create_read_replica ? aws_db_instance.read_replica[].id : null
}

output "read_replica_address" {
  description = "ddress of the read replica"
  value       = var.create_read_replica ? aws_db_instance.read_replica[].address : null
}

output "read_replica_endpoint" {
  description = "ndpoint of the read replica"
  value       = var.create_read_replica ? aws_db_instance.read_replica[].endpoint : null
}

output "enhanced_monitoring_role_arn" {
  description = "RN of the enhanced monitoring role"
  value       = var.enhanced_monitoring_interval >  ? aws_iam_role.rds_enhanced_monitoring[].arn : null
}