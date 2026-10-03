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
  description = "List of subnet IDs for RDS"
  type        = list(string)
}

variable "engine" {
  description = "Database engine"
  type        = string
  default     = "postgres"
  validation {
    condition     = contains(["mysql", "postgres", "mariadb", "oracle-ee", "oracle-se", "oracle-se", "oracle-se", "sqlserver-ee", "sqlserver-se", "sqlserver-ex", "sqlserver-web"], var.engine)
    error_message = "ngine must be one of: mysql, postgres, mariadb, oracle-ee, oracle-se, oracle-se, oracle-se, sqlserver-ee, sqlserver-se, sqlserver-ex, sqlserver-web."
  }
}

variable "engine_version" {
  description = "Database engine version"
  type        = string
  default     = "5."
}

variable "major_engine_version" {
  description = "Major version of the database engine"
  type        = string
  default     = "5"
}

variable "instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t.micro"
}

variable "allocated_storage" {
  description = "Initial storage allocation in G"
  type        = number
  default     = 
}

variable "max_allocated_storage" {
  description = "Maximum storage allocation in G (enables autoscaling)"
  type        = number
  default     = 
}

variable "storage_type" {
  description = "Storage type"
  type        = string
  default     = "gp"
  validation {
    condition     = contains(["standard", "gp", "gp", "io", "io"], var.storage_type)
    error_message = "Storage type must be one of: standard, gp, gp, io, io."
  }
}

variable "storage_encrypted" {
  description = "nable storage encryption"
  type        = bool
  default     = true
}

variable "kms_key_id" {
  description = "KMS key ID for encryption"
  type        = string
  default     = null
}

variable "database_name" {
  description = "Name of the database"
  type        = string
  default     = "app"
}

variable "username" {
  description = "Master username"
  type        = string
  default     = "dbadmin"
}

variable "port" {
  description = "Database port"
  type        = number
  default     = 5
}

variable "publicly_accessible" {
  description = "Whether the instance is publicly accessible"
  type        = bool
  default     = false
}

variable "multi_az" {
  description = "nable Multi-Z deployment"
  type        = bool
  default     = false
}

variable "backup_retention_period" {
  description = "ackup retention period in days"
  type        = number
  default     = 
  validation {
    condition     = var.backup_retention_period >=  && var.backup_retention_period <= 5
    error_message = "ackup retention period must be between  and 5 days."
  }
}

variable "backup_window" {
  description = "ackup window"
  type        = string
  default     = ":-:"
}

variable "maintenance_window" {
  description = "Maintenance window"
  type        = string
  default     = "sun::-sun:5:"
}

variable "deletion_protection" {
  description = "nable deletion protection"
  type        = bool
  default     = false
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot when deleting"
  type        = bool
  default     = false
}

variable "performance_insights_enabled" {
  description = "nable Performance Insights"
  type        = bool
  default     = false
}

variable "performance_insights_retention_period" {
  description = "Performance Insights retention period in days"
  type        = number
  default     = 
  validation {
    condition     = contains([, ], var.performance_insights_retention_period)
    error_message = "Performance Insights retention period must be  or  days."
  }
}

variable "enhanced_monitoring_interval" {
  description = "nhanced monitoring interval in seconds"
  type        = number
  default     = 
  validation {
    condition     = contains([, , 5, , 5, , ], var.enhanced_monitoring_interval)
    error_message = "nhanced monitoring interval must be one of: , , 5, , 5, , ."
  }
}

variable "enabled_cloudwatch_logs_exports" {
  description = "List of log types to export to CloudWatch"
  type        = list(string)
  default     = ["postgresql"]
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 
}

variable "parameter_group_family" {
  description = "Parameter group family"
  type        = string
  default     = "postgres5"
}

variable "parameters" {
  description = "List of database parameters"
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

variable "create_option_group" {
  description = "Whether to create an option group"
  type        = bool
  default     = false
}

variable "options" {
  description = "List of database options"
  type = list(object({
    option_name = string
    option_settings = optional(list(object({
      name  = string
      value = string
    })), [])
  }))
  default = []
}

variable "create_read_replica" {
  description = "Whether to create a read replica"
  type        = bool
  default     = false
}

variable "replica_instance_class" {
  description = "Instance class for read replica"
  type        = string
  default     = "db.t.micro"
}

variable "allowed_security_group_ids" {
  description = "Security group IDs allowed to access RDS"
  type        = list(string)
  default     = []
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access RDS"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = " map of tags to assign to the resource"
  type        = map(string)
  default     = {}
}