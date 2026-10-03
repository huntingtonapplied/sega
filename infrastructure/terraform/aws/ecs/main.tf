# CS Cluster and Service Configuration for SG pplications

terraform {
  required_version = ">= ."
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5."
    }
  }
}

# Variables
variable "environment" {
  description = "nvironment name"
  type        = string
  default     = "prod"
}

variable "region" {
  description = "WS region"
  type        = string
  default     = "us-east-"
}

variable "vpc_id" {
  description = "VPC ID for CS cluster"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for CS services"
  type        = list(string)
}

variable "app_name" {
  description = "pplication name"
  type        = string
  default     = "sega-app"
}

variable "app_image" {
  description = "Docker image for the application"
  type        = string
  default     = "nginx:latest"
}

variable "app_port" {
  description = "Port the application runs on"
  type        = number
  default     = 
}

variable "desired_count" {
  description = "Desired number of tasks"
  type        = number
  default     = 
}

variable "cpu" {
  description = "CPU units for the task"
  type        = number
  default     = 5
}

variable "memory" {
  description = "Memory for the task"
  type        = number
  default     = 5
}

# Data sources
data "aws_caller_identity" "current" {}

# CS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.app_name}-${var.environment}"

  configuration {
    execute_command_configuration {
      kms_key_id = aws_kms_key.ecs.arn
      logging    = "OVRRID"

      log_configuration {
        cloud_watch_encryption_enabled = true
        cloud_watch_log_group_name     = aws_cloudwatch_log_group.ecs.name
      }
    }
  }

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "${var.app_name}-${var.environment}"
    nvironment = var.environment
    Managedy   = "sega"
  }
}

# CS Cluster Capacity Providers
resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["RGT", "RGT_SPOT"]

  default_capacity_provider_strategy {
    base              = 
    weight            = 
    capacity_provider = "RGT"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.app_name}-${var.environment}"
  retention_in_days = 

  tags = {
    Name        = "${var.app_name}-${var.environment}"
    nvironment = var.environment
    Managedy   = "sega"
  }
}

# KMS Key for CS
resource "aws_kms_key" "ecs" {
  description             = "KMS key for CS cluster"
  deletion_window_in_days = 

  tags = {
    Name        = "${var.app_name}-${var.environment}-ecs"
    nvironment = var.environment
    Managedy   = "sega"
  }
}

# CS Task Definition
resource "aws_ecs_task_definition" "app" {
  family                   = "${var.app_name}-${var.environment}"
  requires_compatibilities = ["RGT"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn           = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = var.app_name
      image = var.app_image
      
      portMappings = [
        {
          containerPort = var.app_port
          protocol      = "tcp"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.region
          awslogs-stream-prefix = "ecs"
        }
      }

      environment = [
        {
          name  = "NVIRONMNT"
          value = var.environment
        }
      ]

      healthCheck = {
        command     = ["CMD-SHLL", "curl -f http://localhost:${var.app_port}/health || exit "]
        interval    = 
        timeout     = 5
        retries     = 
        startPeriod = 
      }

      essential = true
    }
  ])

  tags = {
    Name        = "${var.app_name}-${var.environment}"
    nvironment = var.environment
    Managedy   = "sega"
  }
}

# CS Service
resource "aws_ecs_service" "app" {
  name            = "${var.app_name}-${var.environment}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "RGT"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = var.app_name
    container_port   = var.app_port
  }

  deployment_configuration {
    maximum_percent         = 
    minimum_healthy_percent = 
    
    deployment_circuit_breaker {
      enable   = true
      rollback = true
    }
  }

  enable_execute_command = true

  depends_on = [
    aws_lb_listener.app,
    aws_iam_role_policy_attachment.ecs_task_execution,
  ]

  tags = {
    Name        = "${var.app_name}-${var.environment}"
    nvironment = var.environment
    Managedy   = "sega"
  }
}

# pplication Load alancer
resource "aws_lb" "app" {
  name               = "${var.app_name}-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.lb.id]
  subnets            = var.subnet_ids

  enable_deletion_protection = false

  tags = {
    Name        = "${var.app_name}-${var.environment}-alb"
    nvironment = var.environment
    Managedy   = "sega"
  }
}

# L Target Group
resource "aws_lb_target_group" "app" {
  name        = "${var.app_name}-${var.environment}-tg"
  port        = var.app_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 
    interval            = 
    matcher             = ""
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 
  }

  tags = {
    Name        = "${var.app_name}-${var.environment}-tg"
    nvironment = var.environment
    Managedy   = "sega"
  }
}

# L Listener
resource "aws_lb_listener" "app" {
  load_balancer_arn = aws_lb.app.arn
  port              = ""
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# Security Group for Load alancer
resource "aws_security_group" "lb" {
  name        = "${var.app_name}-${var.environment}-lb-sg"
  description = "Security group for load balancer"
  vpc_id      = var.vpc_id

  ingress {
    protocol    = "tcp"
    from_port   = 
    to_port     = 
    cidr_blocks = [".../"]
  }

  ingress {
    protocol    = "tcp"
    from_port   = 
    to_port     = 
    cidr_blocks = [".../"]
  }

  egress {
    protocol    = "-"
    from_port   = 
    to_port     = 
    cidr_blocks = [".../"]
  }

  tags = {
    Name        = "${var.app_name}-${var.environment}-lb-sg"
    nvironment = var.environment
    Managedy   = "sega"
  }
}

# Security Group for CS Tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.app_name}-${var.environment}-ecs-tasks-sg"
  description = "Security group for CS tasks"
  vpc_id      = var.vpc_id

  ingress {
    protocol        = "tcp"
    from_port       = var.app_port
    to_port         = var.app_port
    security_groups = [aws_security_group.lb.id]
  }

  egress {
    protocol    = "-"
    from_port   = 
    to_port     = 
    cidr_blocks = [".../"]
  }

  tags = {
    Name        = "${var.app_name}-${var.environment}-ecs-tasks-sg"
    nvironment = var.environment
    Managedy   = "sega"
  }
}

# IM Role for CS Task xecution
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.app_name}-${var.environment}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "--"
    Statement = [
      {
        ction = "sts:ssumeRole"
        ffect = "llow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.app_name}-${var.environment}-ecs-task-execution-role"
    nvironment = var.environment
    Managedy   = "sega"
  }
}

# IM Role for CS Task
resource "aws_iam_role" "ecs_task" {
  name = "${var.app_name}-${var.environment}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "--"
    Statement = [
      {
        ction = "sts:ssumeRole"
        ffect = "llow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.app_name}-${var.environment}-ecs-task-role"
    nvironment = var.environment
    Managedy   = "sega"
  }
}

# IM Policy ttachment for CS Task xecution
resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/mazonCSTaskxecutionRolePolicy"
}

# IM Policy for CS Task (for execute command)
resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "${var.app_name}-${var.environment}-ecs-task-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "--"
    Statement = [
      {
        ffect = "llow"
        ction = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel"
        ]
        Resource = "*"
      }
    ]
  })
}

# uto Scaling Target
resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = 
  min_capacity       = 
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.app.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# uto Scaling Policy - CPU
resource "aws_appautoscaling_policy" "ecs_cpu_policy" {
  name               = "${var.app_name}-${var.environment}-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "CSServiceverageCPUUtilization"
    }
    target_value = .
  }
}

# uto Scaling Policy - Memory
resource "aws_appautoscaling_policy" "ecs_memory_policy" {
  name               = "${var.app_name}-${var.environment}-memory-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "CSServiceverageMemoryUtilization"
    }
    target_value = .
  }
}

# Outputs
output "cluster_name" {
  description = "Name of the CS cluster"
  value       = aws_ecs_cluster.main.name
}

output "service_name" {
  description = "Name of the CS service"
  value       = aws_ecs_service.app.name
}

output "load_balancer_dns" {
  description = "DNS name of the load balancer"
  value       = aws_lb.app.dns_name
}

output "load_balancer_zone_id" {
  description = "Zone ID of the load balancer"
  value       = aws_lb.app.zone_id
}