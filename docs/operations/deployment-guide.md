# Deployment Guide for SEGA

This guide provides comprehensive instructions for deploying portfolio projects using SEGA at enterprise scale.

## Overview

SEGA provides enterprise-scale deployment orchestration designed for a multi-domain project structure. This guide covers:

- Project configuration with `sega.yaml`
- Multi-project workspace management
- Enterprise deployment orchestration
- Recommended patterns and best practices

## Quick Start

### 1. Initialize a Project

```bash
# Navigate to your project directory
cd /path/to/projects/team/project

# Initialize with a template
sega init --template default --team team-a --project web-app

# Validate configuration
sega doctor --team team-a
```

### 2. Configure Project with sega.yaml

Create a `sega.yaml` file in your project root using a template:

```yaml
version: "2.1"
project:
  name: "web-app"
  type: "web_app"
  domain: "example"
  team: "team-a"
  
# ... (see templates/default/sega.yaml for complete configuration)
```

### 3. Deploy Single Project

**Note**: Deployment commands are being consolidated under `sega ship`. Both `sega deploy` and `sega ship deploy` work during the transition period.

```bash
# Deploy to staging (new command)
sega ship deploy --target staging --strategy rolling

# Deploy to production (new command)
sega ship deploy --target production --strategy canary

# Legacy commands (still supported)
sega deploy --target staging --strategy rolling
sega deploy --target production --strategy canary

# Rollback deployments
sega ship rollback --steps 1
sega ship rollback --version v1.2.3
```

### 4. Build & Publish Artifacts

```bash
# Build for different platforms using sega forge
sega forge build --platform web        # Frontend build
sega forge build --platform api        # Backend build
sega forge build --platform desktop    # Electron build

# Publish to container registry
sega forge publish --target registry

# Full release workflow
sega forge release --platform api --target registry
```

### 5. Deploy Multiple Projects (Workspace)

```bash
# Deploy entire team workspace
sega workspace deploy --target production --team team-a --strategy coordinated

# Deploy specific projects with dependencies
sega workspace deploy --target staging --project team-a/web-app,team-a/api-service
```

## Project Types

SEGA automatically detects and supports the following project types:

### Web Applications
- **Teams**: team-a, team-d, team-e
- **Examples**: web-app, api-service, service-a
- **Features**: React/Node.js, Docker, AWS ECS deployment

### ML/AI Pipelines
- **Teams**: team-c, team-a
- **Examples**: ml-pipeline, service-a/ai
- **Features**: GPU support, model versioning, data pipelines

### Hardware/Firmware Projects
- **Teams**: team-b, team-c
- **Examples**: firmware-service, embedded-service
- **Features**: Cross-compilation, hardware flashing, VPN deployment

### Hybrid Systems
- **Teams**: team-b, team-c
- **Examples**: firmware-service (firmware + UI + RF), embedded-service (gateware + firmware + app)
- **Features**: Multi-domain coordination, component orchestration

### Native Applications
- **Teams**: team-c, team-e
- **Examples**: native-app, rust-service
- **Features**: Native compilation, systemd integration

## Workspace Management

### Discovering Projects

```bash
# List all projects in workspace
sega workspace list

# List projects by team
sega workspace list --team team-a

# List projects by type
sega workspace list --type web_app
```

### Dependency Management

```bash
# Show dependency graph
sega workspace dependencies

# Validate dependencies
sega workspace validate

# Show deployment order
sega workspace deploy --dry-run --team team-a
```

### Coordinated Deployment

```bash
# Deploy with dependency respect
sega workspace deploy --target staging --team team-a --strategy coordinated

# Deploy with maximum parallelism
sega workspace deploy --target staging --team team-a --strategy parallel

# Deploy with fail-fast behavior
sega workspace deploy --target staging --team team-a --strategy fail_fast
```

## Enterprise Orchestration

### Parallel Deployment

SEGA supports enterprise-scale parallel deployment with:

- **Resource constraints**: Maximum concurrent deployments per team/type
- **Dependency resolution**: Automatic ordering based on project dependencies
- **Resource locking**: Shared resource protection during deployment
- **Monitoring**: Real-time deployment status and metrics

```bash
# Deploy with custom parallelism
sega workspace deploy --target staging --strategy parallel --max-workers 20
```

### Deployment Strategies

#### Coordinated Strategy
- Respects all dependencies
- Sequential execution with parallelism where possible
- Automatic rollback on failure

#### Parallel Strategy
- Maximum parallelism within constraints
- Resource-aware scheduling
- Parallel health checks

#### Fail-Fast Strategy
- Stops on first failure
- Immediate rollback
- Detailed error reporting

### Monitoring and Metrics

```bash
# Get deployment status
sega workspace status --team team-a

# Get deployment metrics
sega workspace metrics --team team-a --format json

# Monitor active deployments
sega workspace monitor --team team-a --watch
```

## Organization Features

### Team-Based Organization

```yaml
# sega.yaml
project:
  team: "team-a"  # Auto-detected from directory structure
  
workspace:
  org_workspace:
    cost_center: "team-a-engineering"
    budget_limit: "$2000/month"
    resource_tags:
      Team: "team-a"
      CostCenter: "team-a-engineering"
```

### Security and Compliance

```yaml
# sega.yaml
security:
  compliance:
    frameworks: ["SOC2", "GDPR"]
    data_classification: "internal"
    
  org_security:
    threat_model: "web_application"
    security_contact: "security@example.com"
```

### Integration with Organization Infrastructure

```yaml
# sega.yaml
integrations:
  org_integrations:
    ldap:
      enabled: true
      domain: "example.local"
    
    vault:
      enabled: true
      path: "org/team-a/web-app"
    
    artifactory:
      enabled: true
      repository: "org-team-a"
```

## GitLab CI/CD Integration

Use a GitLab CI template for automated deployment:

```yaml
# .gitlab-ci.yml
include:
  - project: 'org/sega'
    file: '/templates/default/gitlab-ci.yml'

variables:
  SEGA_TEAM: "team-a"
  SEGA_PROJECT: "web-app"
```

## Best Practices

### 1. Project Structure

```
projects/
 team-a/
    web-app/
       sega.yaml
       frontend/
       backend/
       docker-compose.yml
    api-service/
        sega.yaml
        dashboard/
        ai/
 team-b/
    firmware-service/
        sega.yaml
        firmware_engine/
        firmware/
        ui/
 team-c/
     sega/
     ml-pipeline/
         sega.yaml
         ml_engine/
```

### 2. Configuration Management

- Use environment-specific configurations
- Store secrets in your secrets manager (e.g. Vault)
- Tag all resources with team/project/environment

### 3. Dependency Management

- Declare dependencies in `sega.yaml`
- Use shared resources for common infrastructure
- Coordinate deployments for dependent projects

### 4. Monitoring and Alerting

- Configure team-specific alert channels
- Use consistent monitoring namespace conventions
- Set up custom metrics for business logic

## Troubleshooting

### Common Issues

1. **Dependency Resolution Errors**
   ```bash
   sega workspace validate
   sega workspace dependencies --format yaml
   ```

2. **Resource Conflicts**
   ```bash
   sega workspace shared
   sega workspace status --format json
   ```

3. **Deployment Failures**
   ```bash
   sega workspace rollback --target staging --team team-a
   sega logs --target staging --team team-a
   ```

### Support

- **Team-specific support**: Contact your team lead
- **SEGA platform issues**: Create an issue in the `sega` repository
- **Infrastructure issues**: Contact your DevOps team
- **Security concerns**: Contact security@example.com

## Advanced Features

### Custom Deployment Strategies

```python
# Custom deployment plugin
from sega.core.enterprise_orchestrator import EnterpriseOrchestrator

class CustomStrategy:
    def deploy(self, projects, target):
        # Custom deployment logic
        pass
```

### Multi-Region Deployment

```yaml
# sega.yaml
deployment:
  targets:
    production:
      regions:
        - us-east-1
        - us-west-2
      strategy: "multi_region"
```

### Blue-Green Deployment

```yaml
# sega.yaml
deployment:
  targets:
    production:
      strategy: "blue_green"
      traffic_shifting:
        initial: 10%
        increment: 20%
        interval: 300s
```

This guide provides comprehensive coverage of SEGA's enterprise deployment capabilities. For additional information, refer to the complete documentation in the `docs/` directory.

---

## EC2 Deployment Checklist

### Pre-Deployment Prerequisites

#### AWS Infrastructure
- [ ] EC2 instance(s) provisioned with adequate specifications
- [ ] Security groups configured for required ports (22, 80, 443, project ports)
- [ ] Elastic IP addresses assigned if needed
- [ ] Domain/DNS records configured
- [ ] SSL certificates obtained and configured

#### GitLab Configuration
- [ ] GitLab project created or existing project identified
- [ ] GitLab runner tokens generated
- [ ] Project variables configured in GitLab CI/CD settings
- [ ] Ansible inventory file updated with EC2 instance details

### Deployment Steps

#### 1. System Preparation
```bash
# Update Ansible inventory
vim infrastructure/ansible/host.ini

# Test connectivity
ansible all -m ping -i infrastructure/ansible/host.ini
```

#### 2. GitLab Runner Setup
```bash
# Configure runner variables in group_vars or host_vars
# Required variables:
# - gitlab_runner_token
# - gitlab_project_id
# - gitlab_runner_local_tags
# - gitlab_runner_ondemand_tags

# Deploy GitLab runners
ansible-playbook -i infrastructure/ansible/host.ini \
  infrastructure/ansible/playbooks/install_server_jellyfish.yml \
  --tags gitlab_runner
```

#### 3. NGINX Unified Server Configuration
```bash
# Configure unified server for multiple projects
sega unified-server setup --config config/unified_server.yaml

# Verify NGINX configuration
sega unified-server config --validate

# Start unified server
sega unified-server start
```

#### 4. Project Deployment
```bash
# Deploy core infrastructure projects
sega ship deploy --target production --project service-a
sega ship deploy --target production --project service-b
sega ship deploy --target production --project service-c

# Deploy application projects
sega ship deploy --target production --project web-app
sega ship deploy --target production --project api-service
sega ship deploy --target production --project rust-service
```

#### 5. Monitoring and Validation
```bash
# Check unified server status
sega unified-server status

# Validate all services are running
sega status --all-projects

# Run security scans
sega doctor scan --type deps
sega doctor scan --type secrets
```

### Post-Deployment Validation

#### Infrastructure Checks
- [ ] All required services are running
- [ ] Database connections working (PostgreSQL, Redis)
- [ ] NGINX reverse proxy routing correctly
- [ ] SSL certificates valid and auto-renewing
- [ ] Log aggregation working (if configured)

#### Application Checks
- [ ] All project APIs responding (8000-8099 port range)
- [ ] Frontend applications accessible (3000-3099 port range)
- [ ] Mobile endpoints working (4000-4099 port range)
- [ ] Desktop services operational (3300-3399 port range)

#### Security Validation
- [ ] Docker security scan passed
- [ ] Container compliance verified
- [ ] Firewall rules properly configured
- [ ] No exposed secrets or credentials
- [ ] SSL/TLS configuration validated

### GitLab Runner Variables Reference

```yaml
# In group_vars/production.yml or host_vars/[hostname].yml
gitlab_runner_token: "{{ vault_gitlab_runner_token }}"
gitlab_project_id: "your_project_id"

# Optional customizations
gitlab_runner_local_enabled: true
gitlab_runner_local_tags: "production,docker,local"
gitlab_runner_local_description: "Production Docker runner"

gitlab_runner_ondemand_enabled: true
gitlab_runner_ondemand_tags: "production,autoscale"
gitlab_runner_ondemand_description: "Production autoscaling runner"
```

### Rollback Procedures

#### Service Rollback
```bash
# Stop current services
sega unified-server stop

# Restore previous configuration
sega ship rollback --steps 1

# Restart with previous version
sega unified-server start
```

#### Database Rollback
```bash
# Restore database from backup (implementation depends on backup strategy)
# Verify data integrity
sega probe run --type integration --quick
```

### Emergency Procedures

```bash
# Check system health
sega doctor diagnose --all

# View aggregated logs
sega logs --all --tail 100

# Emergency stop all services
sega local down --force
```

#### Monitoring Endpoints
- System status: `https://your-domain/api/health`
- GitLab runner status: `https://gitlab.com/your-project/-/runners`
- Infrastructure metrics: `https://your-domain/monitoring` (if configured)