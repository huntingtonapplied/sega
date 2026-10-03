# Docker Image Build Standards for SEGA Deployment

**Type**: Reference Standard
**Status**: PRODUCTION
**Scope**: SEGA deployment integration

---

## Overview

SEGA-specific standards for Docker image deployment. For comprehensive Docker patterns, see the canonical references:

**Related Documents**:
- **[DOCKER_DEPLOYMENT_PATTERNS.md](/docs/architecture/DOCKER_DEPLOYMENT_PATTERNS.md)** - Dockerfile templates, multi-stage builds, security patterns
- **[CICD_PIPELINE_STANDARDS.md](/docs/standards/deployment/CICD_PIPELINE_STANDARDS.md)** - GitLab CI/CD pipelines, registry management
- **[INFRASTRUCTURE_STANDARDS.md](/docs/standards/deployment/INFRASTRUCTURE_STANDARDS.md)** - Port allocation, environment variables

---

## SEGA Deployment Integration

### Deploy Command Usage

```bash
# Modern Docker registry deployment
sega deploy \
  --image registry.gitlab.com/example-org/web-app:v1.2.3 \
  --environment staging \
  --wait-for-health \
  --setup-nginx \
  --ssl

# With custom port mapping
sega deploy \
  --image registry.gitlab.com/example-org/web-app:latest \
  --environment production \
  --port-mapping "3001:3001,3101:3101" \
  --backup-previous
```

### Required SEGA Compatibility

1. **Health Check Endpoints**: Images must implement `/health` endpoint
2. **Port Standards**: Follow portfolio port allocation (30xx, 31xx ranges)
3. **Environment Variables**: Accept SEGA-provided configuration
4. **Logging**: Support SEGA log aggregation (stdout/stderr)
5. **Non-Root User**: Container must run as non-root (UID 10001-19999)

### SEGA Environment Variables

SEGA injects these environment variables at runtime:

```bash
# Injected by SEGA
SEGA_ENVIRONMENT=production
SEGA_PROJECT_NAME=web-app
METRICS_ENABLED=true
METRICS_TCP_HOST=metrics.example.local
METRICS_TCP_PORT=3308
```

---

## SEGA Validation Commands

### Pre-Deployment Validation

```bash
# Validate Dockerfile compatibility
sega validate --dockerfile Dockerfile --project-type web_app

# Dry-run deployment
sega deploy --dry-run --image registry.gitlab.com/example-org/project:tag

# Check health endpoint
sega health --project project-name --environment staging
```

### Post-Deployment Verification

```bash
# Check deployment status
sega status --project project-name --environment staging

# View deployment logs
sega logs --project project-name --environment staging --tail 50

# Rollback if needed
sega rollback --project project-name --environment staging --version v1.2.2
```

---

## Troubleshooting

### SEGA Integration Issues

```bash
# Validate SEGA deployment
sega deploy --dry-run --image registry.gitlab.com/example-org/project:tag

# Check SEGA status
sega status --project project-name --environment staging

# Debug health check
sega health --project project-name --verbose
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Health check fails | Verify `/health` endpoint returns 200 |
| Port binding fails | Check port allocation in INFRASTRUCTURE_STANDARDS.md |
| Permission denied | Ensure container runs as non-root user |
| Image not found | Verify registry login: `sega auth login --registry gitlab` |

---

## Examples

Complete deployment examples available at:
```
/path/to/sega/examples/docker-registry-deployment/
├── Dockerfile.web-app        # React/Next.js application
├── Dockerfile.api-service    # FastAPI/Express service
├── .gitlab-ci.yml            # Complete CI/CD pipeline
└── docker-compose.yml        # Local development setup
```

---

**Implementation Status**: ✅ PRODUCTION READY
**SEGA Integration**: ✅ FULLY SUPPORTED

---

*For Dockerfile templates and patterns, see [DOCKER_DEPLOYMENT_PATTERNS.md](/docs/architecture/DOCKER_DEPLOYMENT_PATTERNS.md)*
