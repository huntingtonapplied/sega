# SEGA Operations

Operational documentation for deploying and managing SEGA infrastructure.

## 🚨 Critical Troubleshooting

| Document | Purpose |
|----------|---------|
| **[DOCKER_SYSTEM_SERVICE_CONFLICTS.md](DOCKER_SYSTEM_SERVICE_CONFLICTS.md)** ⭐ | **Port conflicts & auto-start issues** - Read this first if containers fail to start |
| [../../scripts/BUILD_SCRIPTS_USAGE.md](../../scripts/BUILD_SCRIPTS_USAGE.md) | Demo vs Development apps - which build scripts to use |

## Deployment Guides

| Document | Purpose |
|----------|---------|
| [deployment-guide.md](deployment-guide.md) | Enterprise deployment procedures |
| [UNIFIED_SERVER_DEPLOYMENT.md](UNIFIED_SERVER_DEPLOYMENT.md) | Unified server configuration |
| [INSTANCE_BUILD_AUTOMATION.md](INSTANCE_BUILD_AUTOMATION.md) | Automated frontend builds for EC2 |
| [hardware-deployment-guide.md](hardware-deployment-guide.md) | Hardware/firmware deployment |
| [LOCAL_DEPLOYMENT_INTEGRATION.md](LOCAL_DEPLOYMENT_INTEGRATION.md) | Local development setup |

## Infrastructure Configuration

| Document | Purpose |
|----------|---------|
| [AWS_SECURITY_GROUP_CONFIGURATION.md](AWS_SECURITY_GROUP_CONFIGURATION.md) | AWS security setup |
| [NGINX_OPERATIONS_GUIDE.md](NGINX_OPERATIONS_GUIDE.md) | Nginx operations and configuration |
| [ansible-role-mapping.md](ansible-role-mapping.md) | Ansible role documentation |

## Testing & Monitoring

| Document | Purpose |
|----------|---------|
| [CONSOLE_SCAN_GUIDE.md](CONSOLE_SCAN_GUIDE.md) | Console scanning and validation |
| [COMPREHENSIVE_DOMAIN_TESTING.md](COMPREHENSIVE_DOMAIN_TESTING.md) | Domain testing procedures |
| [DOMAIN_TESTING_QUICK_REFERENCE.md](DOMAIN_TESTING_QUICK_REFERENCE.md) | Quick domain test commands |

## Quick Commands

```bash
# Deploy to staging
sega ship deploy --target staging

# Deploy to production
sega ship deploy --target production --strategy rolling

# Rollback
sega ship rollback --steps 1

# Check deployment status
sega ship status --watch
```

## EC2 Deployment

See [deployment-guide.md](deployment-guide.md) for the complete EC2 deployment checklist including:

- AWS infrastructure setup
- GitLab runner configuration
- NGINX unified server setup
- Post-deployment validation

## Common Issues

### Container fails with "address already in use"
See **[DOCKER_SYSTEM_SERVICE_CONFLICTS.md](DOCKER_SYSTEM_SERVICE_CONFLICTS.md)** for complete troubleshooting.

Quick fix:
```bash
# Check what's using the port
sudo lsof -i :5009

# If system PostgreSQL
sudo systemctl stop postgresql@16-main
sudo systemctl disable postgresql@16-main
```

### Which build script should I use?
See **[BUILD_SCRIPTS_USAGE.md](../../scripts/BUILD_SCRIPTS_USAGE.md)**

- **Demo apps** (landing-only): Use `build-landing-apps.sh`
- **Development apps** (full stack): Use project's `docker-compose.yml`

## Emergency Procedures

```bash
# System health check
sega doctor diagnose --all

# View logs
sega logs --all --tail 100

# Check all containers
docker ps --format 'table {{.Names}}\t{{.Status}}'

# Check port conflicts
sudo pg_lsclusters
sudo lsof -i :5009

# Emergency stop
sega local down --force
```
