# AWS Security Group Configuration for a Portfolio

**Version**: 1.0
**Authority**: SEGA Infrastructure Division
**Status**: REQUIRED for production deployments
**Created**: 2025-10-06
**Reference**: [PORT_ALLOCATION_STANDARDS.md](/path/to/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md)

## Overview

This document provides efficient AWS Security Group configuration for all portfolio projects, enabling streamlined inbound rule management across the portfolio.

## Port Range Strategy

Instead of creating individual rules for each project port, use **port ranges** to cover all portfolio projects efficiently.

### Production Port Ranges

| Service Type | Port Range | Protocol | Projects Covered | Purpose |
|--------------|------------|----------|------------------|---------|
| **Backend/API** | 8000-8099 | TCP | All 20 projects | REST APIs, gRPC, health checks |
| **Frontend Web** | 3000-3099 | TCP | All 20 projects | Web applications (Next.js, React) |
| **Desktop Apps** | 3300-3399 | TCP | All 20 projects | Electron applications |
| **Mobile Apps** | 19000-19099 | TCP | All 20 projects | Expo development servers |
| **Databases** | 5000-5099 | TCP | All 20 projects | PostgreSQL, TimescaleDB |
| **Redis Cache** | 6000-6099 | TCP | All 20 projects | Redis cache services |
| **Metrics** | 9000-9099 | TCP | All 20 projects | Prometheus, internal metrics |

### Test Environment Port Ranges

| Service Type | Port Range | Protocol | Formula | Purpose |
|--------------|------------|----------|---------|---------|
| **Backend/API (Test)** | 28000-28099 | TCP | prod + 20000 | Test APIs |
| **Frontend (Test)** | 23000-23099 | TCP | prod + 20000 | Test web apps |
| **Databases (Test)** | 25000-25099 | TCP | prod + 20000 | Test databases |
| **Redis (Test)** | 26000-26099 | TCP | prod + 20000 | Test caches |
| **Metrics (Test)** | 29000-29099 | TCP | prod + 20000 | Test metrics |

### Standard Infrastructure Ports

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| **HTTP** | 80 | TCP | NGINX HTTP traffic |
| **HTTPS** | 443 | TCP | NGINX HTTPS traffic |
| **SSH** | 22 | TCP | Server administration |

## AWS Security Group Configuration

### Method 1: AWS Console (Recommended for Quick Setup)

1. **Navigate to EC2 Console** → Security Groups
2. **Select or Create Security Group**
3. **Add Inbound Rules**:

#### Production Environment Rules
```
Type: Custom TCP
Port Range: 8000-8099
Source: 0.0.0.0/0
Description: Backend APIs (all projects)

Type: Custom TCP
Port Range: 3000-3099
Source: 0.0.0.0/0
Description: Frontend Web Applications (all projects)

Type: Custom TCP
Port Range: 3300-3399
Source: 0.0.0.0/0
Description: Desktop Applications (all projects)

Type: Custom TCP
Port Range: 19000-19099
Source: 0.0.0.0/0
Description: Mobile Applications (all projects)

Type: Custom TCP
Port Range: 5000-5099
Source: [your-trusted-ips]/32
Description: Databases (restrict to trusted IPs)

Type: Custom TCP
Port Range: 6000-6099
Source: [your-trusted-ips]/32
Description: Redis Cache (restrict to trusted IPs)

Type: Custom TCP
Port Range: 9000-9099
Source: [your-trusted-ips]/32
Description: Metrics (restrict to trusted IPs)

Type: HTTP
Port: 80
Source: 0.0.0.0/0
Description: NGINX HTTP

Type: HTTPS
Port: 443
Source: 0.0.0.0/0
Description: NGINX HTTPS

Type: SSH
Port: 22
Source: [your-ip]/32
Description: SSH access (restrict to your IP)
```

### Method 2: AWS CLI (Recommended for Automation)

Create security group with Terraform or AWS CLI:

```bash
#!/bin/bash
# AWS Security Group Configuration for a Portfolio

SECURITY_GROUP_ID="sg-xxxxxxxxx"  # Replace with your security group ID
REGION="us-east-2"  # Replace with your region

# Backend APIs (8000-8099)
aws ec2 authorize-security-group-ingress \
  --group-id $SECURITY_GROUP_ID \
  --region $REGION \
  --ip-permissions IpProtocol=tcp,FromPort=8000,ToPort=8099,IpRanges='[{CidrIp=0.0.0.0/0,Description="Backend APIs"}]'

# Frontend Web (3000-3099)
aws ec2 authorize-security-group-ingress \
  --group-id $SECURITY_GROUP_ID \
  --region $REGION \
  --ip-permissions IpProtocol=tcp,FromPort=3000,ToPort=3099,IpRanges='[{CidrIp=0.0.0.0/0,Description="Frontend Web"}]'

# Desktop Apps (3300-3399)
aws ec2 authorize-security-group-ingress \
  --group-id $SECURITY_GROUP_ID \
  --region $REGION \
  --ip-permissions IpProtocol=tcp,FromPort=3300,ToPort=3399,IpRanges='[{CidrIp=0.0.0.0/0,Description="Desktop Apps"}]'

# Mobile Apps (19000-19099)
aws ec2 authorize-security-group-ingress \
  --group-id $SECURITY_GROUP_ID \
  --region $REGION \
  --ip-permissions IpProtocol=tcp,FromPort=19000,ToPort=19099,IpRanges='[{CidrIp=0.0.0.0/0,Description="Mobile Apps"}]'

# Databases (5000-5099) - RESTRICT TO TRUSTED IPs
aws ec2 authorize-security-group-ingress \
  --group-id $SECURITY_GROUP_ID \
  --region $REGION \
  --ip-permissions IpProtocol=tcp,FromPort=5000,ToPort=5099,IpRanges='[{CidrIp=YOUR_IP/32,Description="Databases"}]'

# Redis (6000-6099) - RESTRICT TO TRUSTED IPs
aws ec2 authorize-security-group-ingress \
  --group-id $SECURITY_GROUP_ID \
  --region $REGION \
  --ip-permissions IpProtocol=tcp,FromPort=6000,ToPort=6099,IpRanges='[{CidrIp=YOUR_IP/32,Description="Redis Cache"}]'

# Metrics (9000-9099) - RESTRICT TO TRUSTED IPs
aws ec2 authorize-security-group-ingress \
  --group-id $SECURITY_GROUP_ID \
  --region $REGION \
  --ip-permissions IpProtocol=tcp,FromPort=9000,ToPort=9099,IpRanges='[{CidrIp=YOUR_IP/32,Description="Metrics"}]'

# Standard Infrastructure
aws ec2 authorize-security-group-ingress \
  --group-id $SECURITY_GROUP_ID \
  --region $REGION \
  --ip-permissions IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges='[{CidrIp=0.0.0.0/0,Description="HTTP"}]'

aws ec2 authorize-security-group-ingress \
  --group-id $SECURITY_GROUP_ID \
  --region $REGION \
  --ip-permissions IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges='[{CidrIp=0.0.0.0/0,Description="HTTPS"}]'

aws ec2 authorize-security-group-ingress \
  --group-id $SECURITY_GROUP_ID \
  --region $REGION \
  --ip-permissions IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges='[{CidrIp=YOUR_IP/32,Description="SSH"}]'
```

### Method 3: Terraform (Recommended for Infrastructure as Code)

```hcl
# terraform/security-groups/portfolio.tf

resource "aws_security_group" "portfolio" {
  name        = "portfolio-sg"
  description = "Security group for the portfolio"
  vpc_id      = var.vpc_id

  # Backend APIs (8000-8099)
  ingress {
    description = "Backend APIs"
    from_port   = 8000
    to_port     = 8099
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Frontend Web (3000-3099)
  ingress {
    description = "Frontend Web Applications"
    from_port   = 3000
    to_port     = 3099
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Desktop Apps (3300-3399)
  ingress {
    description = "Desktop Applications"
    from_port   = 3300
    to_port     = 3399
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Mobile Apps (19000-19099)
  ingress {
    description = "Mobile Applications"
    from_port   = 19000
    to_port     = 19099
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Databases (5000-5099) - Restricted
  ingress {
    description = "Databases (restricted)"
    from_port   = 5000
    to_port     = 5099
    protocol    = "tcp"
    cidr_blocks = var.trusted_database_ips
  }

  # Redis (6000-6099) - Restricted
  ingress {
    description = "Redis Cache (restricted)"
    from_port   = 6000
    to_port     = 6099
    protocol    = "tcp"
    cidr_blocks = var.trusted_database_ips
  }

  # Metrics (9000-9099) - Restricted
  ingress {
    description = "Metrics (restricted)"
    from_port   = 9000
    to_port     = 9099
    protocol    = "tcp"
    cidr_blocks = var.trusted_monitoring_ips
  }

  # HTTP
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # SSH
  ingress {
    description = "SSH (restricted)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.admin_ips
  }

  # Egress (allow all outbound)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "portfolio-sg"
    Environment = var.environment
    ManagedBy   = "SEGA"
  }
}

# Variables
variable "vpc_id" {
  description = "VPC ID for security group"
  type        = string
}

variable "trusted_database_ips" {
  description = "Trusted IPs for database access"
  type        = list(string)
  default     = ["192.0.2.0/24"]  # Replace with your trusted IPs
}

variable "trusted_monitoring_ips" {
  description = "Trusted IPs for metrics access"
  type        = list(string)
  default     = ["192.0.2.0/24"]  # Replace with your trusted IPs
}

variable "admin_ips" {
  description = "Admin IPs for SSH access"
  type        = list(string)
  # MUST be overridden - no default for security
}

variable "environment" {
  description = "Environment name (production/staging/development)"
  type        = string
  default     = "production"
}
```

## Security Best Practices

### 1. Principle of Least Privilege

**Public Access** (0.0.0.0/0):
- ✅ Backend APIs (8000-8099) - Required for external clients
- ✅ Frontend Web (3000-3099) - Required for web browsers
- ✅ Desktop Apps (3300-3399) - Required for desktop clients
- ✅ Mobile Apps (19000-19099) - Required for mobile development
- ✅ HTTP/HTTPS (80/443) - Required for web traffic

**Restricted Access** (specific IPs):
- 🔒 Databases (5000-5099) - Internal/VPN only
- 🔒 Redis (6000-6099) - Internal/VPN only
- 🔒 Metrics (9000-9099) - Monitoring systems only
- 🔒 SSH (22) - Admin IPs only

### 2. Environment Separation

Create separate security groups for different environments:

- **Production**: `portfolio-production-sg`
- **Staging**: `portfolio-staging-sg`
- **Development**: `portfolio-development-sg`

### 3. VPC and Private Subnets

For production deployments:
1. **Public Subnet**: Frontend applications, load balancers
2. **Private Subnet**: Databases, Redis, internal services
3. **Security Group Isolation**: Services in private subnets should NOT have public inbound rules

### 4. Use Application Load Balancer (ALB)

Instead of exposing individual ports, use ALB:
```
Internet → ALB (80/443) → Target Groups → Backend Services (8000-8099)
```

Benefits:
- Single entry point (80/443)
- SSL termination
- Path-based routing
- Health checks
- Auto-scaling support

## SEGA Integration

### Automated Security Group Management

SEGA can automate security group configuration:

```bash
# Deploy with automatic security group configuration
sega deploy --environment production --configure-security-groups

# Verify security group configuration
sega infrastructure verify-security-groups

# Update security group for new project
sega infrastructure add-project-ports --project newproject --ports 8020,3020,5020,6020
```

### Port Conflict Detection

Before deployment, SEGA checks port availability:

```bash
# Check if ports are accessible
sega infrastructure check-ports --environment production

# Verify security group rules match port standards
sega infrastructure audit-security-groups
```

## Monitoring and Compliance

### CloudWatch Alarms

Monitor security group changes:
```bash
# Alert on security group modifications
aws cloudwatch put-metric-alarm \
  --alarm-name portfolio-security-group-changes \
  --alarm-description "Alert on security group modifications" \
  --metric-name SecurityGroupEventCount \
  --namespace AWS/CloudTrail \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold
```

### Regular Audits

Schedule quarterly reviews:
1. **Review inbound rules** - Remove unused ports
2. **Verify IP restrictions** - Update trusted IPs
3. **Check compliance** - Ensure alignment with port standards
4. **Test access** - Verify services are accessible

## Troubleshooting

### Service Not Accessible

1. **Check Security Group**: Verify port range includes your service port
2. **Check NACL**: Network ACLs may also block traffic
3. **Check Instance**: Verify service is listening on 0.0.0.0 (not 127.0.0.1)
4. **Check Routing**: Verify route tables and internet gateway

### Commands for Diagnostics

```bash
# Check what's listening on a port
netstat -tlnp | grep :8015

# Test connectivity from external
curl -v http://[external-ip]:8015/health

# Test connectivity from internal
curl -v http://localhost:8015/health

# Check security group rules
aws ec2 describe-security-groups \
  --group-ids sg-xxxxxxxxx \
  --region us-east-2
```

## Migration Guide

### From Individual Port Rules to Port Ranges

If you currently have individual rules for each project:

1. **Document existing rules**: `aws ec2 describe-security-groups`
2. **Create new port range rules**: Use methods above
3. **Test connectivity**: Verify all services work
4. **Remove old rules**: Clean up individual port rules
5. **Monitor**: Check CloudWatch for any connection issues

### Expected Results

**Before** (inefficient):
- 20 projects × 7 ports = 140 individual inbound rules

**After** (optimized):
- 7 port range rules covering all projects
- 3 standard infrastructure rules (HTTP/HTTPS/SSH)
- **Total: 10 rules** instead of 140+

## Summary

**Efficient Configuration**: Instead of 140+ individual port rules, use **7 port range rules** to cover all portfolio projects:

1. `8000-8099`: Backend APIs
2. `3000-3099`: Frontend Web
3. `3300-3399`: Desktop Apps
4. `19000-19099`: Mobile Apps
5. `5000-5099`: Databases (restricted)
6. `6000-6099`: Redis (restricted)
7. `9000-9099`: Metrics (restricted)

Plus standard infrastructure: HTTP (80), HTTPS (443), SSH (22)

**Security Principle**: Public application ports, private infrastructure ports, restricted admin access.

---

**File Reference**: `docs/operations/AWS_SECURITY_GROUP_CONFIGURATION.md`
**Authority**: SEGA Infrastructure Division
**Related Standards**: [PORT_ALLOCATION_STANDARDS.md](/path/to/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md)
