# CS Module for SG Infrastructure
terraform {
  required_version = ">= ."
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5."
    }
  }
}

# CS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = var.enable_container_insights ? "enabled" : "disabled"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-cluster"
  })
}

# CS Cluster Capacity Providers
resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = var.capacity_providers

  dynamic "default_capacity_provider_strategy" {
    for_each = var.capacity_providers
    content {
      capacity_provider = default_capacity_provider_strategy.value
      weight           = 
      base            = 
    }
  }
}

# CloudWatch Log Group for CS tasks
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ecs-logs"
  })
}

# IM Role for CS Task xecution
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-${var.environment}-ecs-task-execution"

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

  tags = var.tags
}

# ttach the CS task execution policy
resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/mazonCSTaskxecutionRolePolicy"
}

# dditional policy for CR and Secrets Manager access
resource "aws_iam_role_policy" "ecs_task_execution_additional" {
  name = "${var.project_name}-${var.environment}-ecs-task-execution-additional"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "--"
    Statement = [
      {
        ffect = "llow"
        ction = [
          "ecr:GetuthorizationToken",
          "ecr:atchCheckLayervailability",
          "ecr:GetDownloadUrlorLayer",
          "ecr:atchGetImage"
        ]
        Resource = "*"
      },
      {
        ffect = "llow"
        ction = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:*:*:secret:${var.project_name}/${var.environment}/*"
      },
      {
        ffect = "llow"
        ction = [
          "logs:CreateLogStream",
          "logs:PutLogvents"
        ]
        Resource = "${aws_cloudwatch_log_group.ecs.arn}:*"
      }
    ]
  })
}

# IM Role for CS Tasks (application role)
resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-${var.environment}-ecs-task"

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

  tags = var.tags
}

# Security Group for CS tasks
resource "aws_security_group" "ecs_tasks" {
  name_prefix = "${var.project_name}-${var.environment}-ecs-tasks"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = var.alb_security_group_ids
    cidr_blocks     = var.allowed_cidr_blocks
  }

  egress {
    from_port   = 
    to_port     = 
    protocol    = "-"
    cidr_blocks = [".../"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ecs-tasks-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# pplication Load alancer (if enabled)
resource "aws_lb" "main" {
  count = var.create_load_balancer ?  : 

  name               = "${var.project_name}-${var.environment}-alb"
  internal           = var.internal_load_balancer
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb[].id]
  subnets            = var.subnet_ids

  enable_deletion_protection = var.enable_deletion_protection

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-alb"
  })
}

# Security Group for L
resource "aws_security_group" "alb" {
  count = var.create_load_balancer ?  : 

  name_prefix = "${var.project_name}-${var.environment}-alb"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 
    to_port     = 
    protocol    = "tcp"
    cidr_blocks = [".../"]
  }
  
  ingress {
    from_port   = 
    to_port     = 
    protocol    = "tcp"
    cidr_blocks = [".../"]
  }

  egress {
    from_port   = 
    to_port     = 
    protocol    = "-"
    cidr_blocks = [".../"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-alb-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# L Target Group
resource "aws_lb_target_group" "main" {
  count = var.create_load_balancer ?  : 

  name        = "${var.project_name}-${var.environment}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 
    interval            = 
    matcher             = ""
    path                = var.health_check_path
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-tg"
  })
}

# L Listener
resource "aws_lb_listener" "main" {
  count = var.create_load_balancer ?  : 

  load_balancer_arn = aws_lb.main[].arn
  port              = ""
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main[].arn
  }

  tags = var.tags
}

# WS Certificate Manager Certificate
resource "aws_acm_certificate" "main" {
  count = var.create_load_balancer && var.domain_name != "" ?  : 

  domain_name       = "${var.project_name}.${var.domain_name}"
  validation_method = "DNS"

  subject_alternative_names = [
    "*.${var.domain_name}"
  ]

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ssl-cert"
  })
}

# HTTPS L Listener
resource "aws_lb_listener" "https" {
  count = var.create_load_balancer && var.domain_name != "" ?  : 

  load_balancer_arn = aws_lb.main[].arn
  port              = ""
  protocol          = "HTTPS"
  ssl_policy        = "LSecurityPolicy-TLS----"
  certificate_arn   = aws_acm_certificate.main[].arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main[].arn
  }

  tags = var.tags
}

# HTTP to HTTPS Redirect Listener
resource "aws_lb_listener" "http_redirect" {
  count = var.create_load_balancer && var.domain_name != "" ?  : 

  load_balancer_arn = aws_lb.main[].arn
  port              = ""
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = ""
      protocol    = "HTTPS"
      status_code = "HTTP_"
    }
  }

  tags = var.tags
}