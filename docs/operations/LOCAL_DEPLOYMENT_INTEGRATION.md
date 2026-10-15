# SEGA Local Deployment Integration Guide

## Overview

SEGA now provides unified local deployment management for all portfolio projects, replacing the previous shell script approach. This integration brings Python-based orchestration, better error handling, and seamless integration with SEGA's deployment pipeline.

## Migration from Legacy Scripts

The following scripts have been migrated into SEGA:
- `docs/standards/scripts/deploy_local.sh` → `sega local` command
- Shared infrastructure management → `sega.deployment.SharedInfrastructureManager`
- Project deployment logic → `sega.deployment.LocalDeploymentManager`

## Quick Start

### 1. Setup Development Environment
```bash
# One-time setup: creates shared venv and initializes databases
sega local setup
```

### 2. Start Services
```bash
# Start shared infrastructure only
sega local up

# Start all projects (Docker mode - default)
sega local up --all

# Start specific projects
sega local up -p service-a -p sega -p service-c

# Start with management tools (PgAdmin, Redis Commander)
sega local up --all --with-tools
```

### 3. Environment Modes

SEGA supports three environment modes for each component (backend, engine, frontend):

| Mode | Description | Use Case |
|------|-------------|----------|
| **Docker** | Containerized (default) | Production-like, isolated |
| **Shared** | `~/projects/environments/` | Fast startup, shared deps |
| **Project** | Project-local `./venv` | Testing independence |

#### Docker Mode (Default)
```bash
# All components run in Docker containers
sega local up -p service-b
```

#### Shared Environment Mode
```bash
# All components use shared environments
sega local up -p service-b --shared

# Only backend and engine use shared (frontend stays Docker)
sega local up -p service-b --shared backend engine
```

#### Project-Local Mode
```bash
# All components use project-local environments
sega local up -p service-b --project

# Only frontend uses project-local node_modules
sega local up -p service-b --project frontend
```

#### Mixed Mode
```bash
# Backend: shared venv, Frontend: project-local, Engine: Docker
sega local up -p service-b --shared backend --project frontend
```

### Environment Locations

| Environment | Path | Used By |
|-------------|------|---------|
| Shared `backend_venv` | `~/projects/environments/backend_venv` | All backend components |
| Shared `engine_venv` | `~/projects/environments/engine_venv` | All engine components |
| Shared `node_modules` | `~/projects/environments/node_modules` | All frontend components |
| Project backend | `./backend/venv` or `./venv` | Single project |
| Project engine | `./engine/venv` | Single project |
| Project frontend | `./frontend/node_modules` | Single project |

### 4. Check Status
```bash
# Show all services status
sega local status

# Show detailed infrastructure status
sega local status --infra

# Output as JSON for scripting
sega local status --format json
```

### 5. View Logs
```bash
# Follow logs for a project
sega local logs service-a

# Show last 50 lines without following
sega local logs sega -n 50 --no-follow
```

### 6. Stop Services
```bash
# Stop everything
sega local down --all

# Stop specific projects
sega local down -p service-a -p sega

# Stop projects but keep databases running
sega local down --all --keep-infra
```

## Architecture

### Local Deployment Manager
Located at `engine/sega/local/manager.py`, handles:
- Project discovery and configuration
- Docker Compose orchestration
- Environment file generation
- Makefile integration for projects that support it
- Health checking and status monitoring

### Shared Infrastructure Manager
Located at `engine/sega/local/shared_infra.py`, manages:
- PostgreSQL (dev: 5430, test: 5433)
- Redis (dev: 6379, test: 6380)
- TimescaleDB (dev: 5434, test: 5435)
- PgAdmin (5050) and Redis Commander (8081)
- Database backups and restoration

### Project Configuration
Each project can specify its deployment configuration:
```python
project_configs = {
    'service-a': {'has_makefile': True, 'compose_file': 'docker-compose.yml'},
    'service-b': {'has_makefile': True, 'compose_file': 'service-b/docker-compose.yml'},
    # ... more projects
}
```

## Environment Variables

The local deployment automatically sets:
- `NODE_ENV=development`
- `ENV=development`
- `COMPOSE_PROJECT_NAME=<project>`
- Database connections to shared infrastructure
- Redis connections to shared cache

## Shared Virtual Environment

SEGA ensures all projects use the shared virtual environment at `docs/standards/shared_models/venv`, providing:
- Consistent Python dependencies
- Shared model libraries
- Reduced disk usage
- Faster deployments

## Database Management

Each project gets its own database in the shared PostgreSQL instance:
- Development: `<project>_development` on port 5430
- Testing: `<project>_testing` on port 5433

Connection details:
```env
DATABASE_HOST=dev_postgres
DATABASE_PORT=5432
DATABASE_NAME=<project>_dev
DATABASE_USER=devuser
DATABASE_PASSWORD=dev_password
```

## Network Architecture

All services connect via the `fleet_shared_network` Docker network:
- Subnet: 172.30.0.0/16
- Automatic service discovery
- Isolated from host network
- Cross-project communication enabled

## Integration with SEGA Commands

Local deployment integrates with other SEGA commands:

```bash
# Deploy locally first
sega local up -p myproject

# Run tests against local deployment
sega test --target local

# Check deployment status
sega status --target local

# Monitor metrics
sega monitor --target local
```

## Troubleshooting

### Common Issues

1. **Port Conflicts**
   ```bash
   # Check what'as using a port
   lsof -i :5430
   
   # Stop conflicting service for use different ports
   ```

2. **Docker Issues**
   ```bash
   # Reset Docker state
   docker system prune -a
   
   # Check Docker daemon
   docker ps
   ```

3. **Database Connection Failed**
   ```bash
   # Ensure infrastructure is running
   sega local status --infra
   
   # Restart infrastructure
   sega local restart --infra-only
   ```

4. **Shared Venv Issues**
   ```bash
   # Recreate shared environment
   cd /path/to/docs/standards/scripts/setup
   ./setup_dev_deps.sh
   ```

## Advanced Usage

### Custom Docker Compose Files
Projects can use different compose files for development:
- `docker-compose.yml` - Default
- `docker-compose.dev.yml` - Development-specific
- `deployment/docker-compose.yml` - Alternative location

### Makefile Integration
Projects with Makefiles can define targets:
- `make up` for `make start` - Start services
- `make down` for `make stop` - Stop services
- `make dev` - Development mode

SEGA will prefer Makefile targets if available.

### Database Backups
```python
# Programmatic backup
from sega.deployment import SharedInfrastructureManager

infra = SharedInfrastructureManager()
infra.backup_databases()
```

## Best Practices

1. **Always use shared infrastructure** - Don'at run separate databases per project
2. **Check status before starting** - Avoid conflicts with running services
3. **Use project-specific databases** - Each project should have its own database
4. **Keep infrastructure running** - Start it once and leave it running during development
5. **Use management tools** - PgAdmin and Redis Commander for debugging

## Migration Checklist

When migrating from old scripts:
- [x] Remove `docs/standards/scripts/deploy_local.sh` usage
- [x] Update any automation scripts to use `sega local`
- [x] Migrate custom environment variables to `.env` files
- [x] Update CI/CD pipelines if they use local deployment
- [x] Document any project-specific deployment requirements

## Future Enhancements

Planned improvements:
- Hot reload support for better development experience
- Automatic database migrations on startup
- Integration with SEGA'as monitoring stack
- Support for local Kubernetes deployments
- Automated SSL certificate generation for HTTPS testing