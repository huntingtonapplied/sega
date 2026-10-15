# VPC Module for SG Infrastructure
terraform {
  required_version = ">= ."
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5."
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-vpc"
  })
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-igw"
  })
}

# Public Subnets
resource "aws_subnet" "public" {
  count = var.availability_zones

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, , count.index + )
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-public-${count.index + }"
    Type = "public"
  })
}

# Private Subnets
resource "aws_subnet" "private" {
  count = var.availability_zones

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, , count.index + )
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-private-${count.index + }"
    Type = "private"
  })
}

# lastic IPs for NT Gateways
resource "aws_eip" "nat" {
  count = var.enable_nat_gateway ? var.availability_zones : 

  domain = "vpc"
  depends_on = [aws_internet_gateway.main]

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-nat-eip-${count.index + }"
  })
}

# NT Gateways
resource "aws_nat_gateway" "main" {
  count = var.enable_nat_gateway ? var.availability_zones : 

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-nat-${count.index + }"
  })

  depends_on = [aws_internet_gateway.main]
}

# Route Table for Public Subnets
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = ".../"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-public-rt"
  })
}

# Route Table ssociations for Public Subnets
resource "aws_route_table_association" "public" {
  count = var.availability_zones

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Route Tables for Private Subnets
resource "aws_route_table" "private" {
  count = var.availability_zones

  vpc_id = aws_vpc.main.id

  dynamic "route" {
    for_each = var.enable_nat_gateway ? [] : []
    content {
      cidr_block     = ".../"
      nat_gateway_id = aws_nat_gateway.main[count.index].id
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-private-rt-${count.index + }"
  })
}

# Route Table ssociations for Private Subnets
resource "aws_route_table_association" "private" {
  count = var.availability_zones

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# VPC ndpoints for WS Services (optional)
resource "aws_vpc_endpoint" "s" {
  count = var.enable_vpc_endpoints ?  : 

  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${data.aws_region.current.name}.s"

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-s-endpoint"
  })
}

resource "aws_vpc_endpoint" "ecr_api" {
  count = var.enable_vpc_endpoints ?  : 

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[].id]
  private_dns_enabled = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ecr-api-endpoint"
  })
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  count = var.enable_vpc_endpoints ?  : 

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[].id]
  private_dns_enabled = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ecr-dkr-endpoint"
  })
}

# Security Group for VPC ndpoints
resource "aws_security_group" "vpc_endpoints" {
  count = var.enable_vpc_endpoints ?  : 

  name_prefix = "${var.project_name}-${var.environment}-vpc-endpoints"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 
    to_port     = 
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 
    to_port     = 
    protocol    = "-"
    cidr_blocks = [".../"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-vpc-endpoints-sg"
  })
}

# Get current region
data "aws_region" "current" {}