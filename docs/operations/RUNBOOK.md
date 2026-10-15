# SEGA Operations Runbook

Operational procedures for SEGA deployments and troubleshooting.

## Quick Reference

### Service Health Check
```bash
sega doctor check
sega health --all-services
```

### Emergency Rollback
```bash
sega ship rollback --project <name> --environment <env>
```

### View Logs
```bash
sega local logs <project>
sega logs --project <name> --environment <env> --tail 100
```

---

## Common Operations

### Starting Local Development
```bash
# Full Docker mode
sega local up

# Hybrid mode (databases in Docker, apps native)
sega local up --mode hybrid

# Check status
sega local status
```

### Deploying a Project
```bash
# Dry run first
sega ship deploy --project <name> --environment staging --dry-run

# Actual deployment
sega ship deploy --project <name> --environment staging

# Verify health
sega health --project <name> --environment staging
```

### Troubleshooting Deployments

#### Container Won't Start
1. Check logs: `sega local logs <project>`
2. Validate config: `sega validate --dockerfile Dockerfile`
3. Check ports: `sega doctor diagnose --network`
4. Verify health endpoint: `curl localhost:<port>/health`

#### Health Check Failing
1. Verify `/health` endpoint exists
2. Check port binding
3. Review container logs
4. Test with: `sega health --project <name> --wait --timeout 60`

#### Database Connection Issues
1. Check shared infrastructure: `sega local status`
2. Verify port allocation (50xx range)
3. Check environment variables
4. Restart databases: `sega local down && sega local up`

---

## Emergency Procedures

### Full System Recovery
```bash
# Stop all services
sega local down

# Clear Docker state
docker system prune -f

# Restart infrastructure
sega local up

# Verify health
sega doctor check
```

### Rolling Back Multiple Projects
```bash
# Check deployment history
sega ship status --project <name> --history

# Rollback each project
for project in service-a service-b service-c; do
  sega ship rollback --project $project --environment production
done
```

---

## Reference

- [LOCAL_DEPLOYMENT_INTEGRATION.md](LOCAL_DEPLOYMENT_INTEGRATION.md) - Local deployment details
- [UNIFIED_SERVER_DEPLOYMENT.md](UNIFIED_SERVER_DEPLOYMENT.md) - Unified server setup
- [AWS_SECURITY_GROUP_CONFIGURATION.md](AWS_SECURITY_GROUP_CONFIGURATION.md) - AWS security groups
