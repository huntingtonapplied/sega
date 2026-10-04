# SEGA Frontend Orchestration Guide

**Purpose**: Group-based frontend build and serve orchestration for your projects
**Command**: `sega frontend`
**Last Updated**: 2025-12-13

## Overview

The `sega frontend` command provides powerful orchestration for building and serving multiple Next.js frontends across EC2 instances. It supports both **shared** and **isolated** dependency modes for flexible development and production workflows.

## Quick Start

```bash
# Build all frontends in Group 1 using shared dependencies
sega frontend build --group group1 --mode shared

# Serve all frontends in Group 1
sega frontend serve --group group1 --mode shared

# Build and serve in one command
sega frontend up --group group1 --mode shared

# Check status of all frontends
sega frontend status --group all
```

## Project Groups

Groups are defined in `/sega/config/unified_server.yaml`:

| Group | Instance | IP | Projects |
|-------|----------|-----|----------|
| **group1** | prod-01 | 203.0.113.10 | service-a, service-b, service-c, service-d, service-e, service-f, service-g, service-h |
| **group2** | prod-02 | 203.0.113.11 | service-i, service-j, service-k, service-l, service-m, service-n, service-o, web-app |
| **group3** | prod-02 | 203.0.113.11 | service-p, service-q |

## Dependency Modes

### Shared Mode (Recommended for Development)

Uses centralized dependencies from `~/portfolio/environments/`:

```bash
sega frontend build --group group1 --mode shared
```

**How it works:**
- Creates symlink: `project/frontend/node_modules` → `~/portfolio/environments/node_modules`
- All projects share the same Node.js dependencies
- Faster builds (no duplicate `npm install`)
- Lower disk usage

**Shared environment structure:**
```
~/portfolio/environments/
├── node_modules/        # Shared Node.js dependencies
├── package.json         # Unified package.json
├── backend_venv/        # Shared Python venv
└── engine_venv/         # Shared engine venv
```

### Isolated Mode (Recommended for Production)

Uses project-specific dependencies:

```bash
sega frontend build --group group1 --mode isolated
```

**How it works:**
- Each project has its own `node_modules/`
- Runs `npm install` in each project's frontend directory
- Ensures version isolation between projects
- Recommended for production deployments

## Commands

### `sega frontend build`

Build frontend assets for projects in a group.

```bash
sega frontend build --group GROUP [--mode MODE] [--parallel N] [--project PROJECT]

Options:
  --group      Project group to build (group1, group2, group3, all)
  --mode       Dependency mode: shared or isolated (default: shared)
  --parallel   Max concurrent builds (default: 4)
  --project    Build specific project(s) instead of group
  --clean      Clean .next directory before build
  --dry-run    Show what would be built without executing
  --remote     Execute on remote EC2 instance (auto-detects from group)
```

**Examples:**
```bash
# Build all Group 1 frontends
sega frontend build --group group1

# Build with isolated dependencies
sega frontend build --group group1 --mode isolated

# Build specific projects
sega frontend build --project service-c --project service-e

# Clean build
sega frontend build --group group1 --clean

# Build on remote EC2 Instance 1 (group1 projects)
sega frontend build --group group1 --remote

# Build on remote EC2 Instance 2 (group2 projects)
sega frontend build --group group2 --remote
```

### `sega frontend serve`

Start frontend servers for projects in a group.

```bash
sega frontend serve --group GROUP [--mode MODE] [--dev] [--port-offset N]

Options:
  --group        Project group to serve (group1, group2, group3, all)
  --mode         Dependency mode: shared or isolated (default: shared)
  --dev          Use development server (npm run dev) instead of production
  --port-offset  Offset from standard ports (for multiple instances)
  --background   Run servers in background
  --remote       Execute on remote EC2 instance (auto-detects from group)
```

**Examples:**
```bash
# Serve all Group 1 frontends (production mode)
sega frontend serve --group group1

# Serve in development mode
sega frontend serve --group group1 --dev

# Run in background
sega frontend serve --group group1 --background

# Serve on remote EC2 Instance 1
sega frontend serve --group group1 --remote

# Serve on remote EC2 Instance 2
sega frontend serve --group group2 --remote
```

### `sega frontend up`

Combined build and serve command.

```bash
sega frontend up --group GROUP [--mode MODE] [--dev] [--skip-build]

Options:
  --group       Project group (group1, group2, group3, all)
  --mode        Dependency mode: shared or isolated (default: shared)
  --dev         Use development servers
  --skip-build  Skip build step, only serve
  --clean       Clean before build
```

**Examples:**
```bash
# Full deployment: build + serve
sega frontend up --group group1 --mode shared

# Quick restart (skip build)
sega frontend up --group group1 --skip-build

# Development mode
sega frontend up --group group1 --dev
```

### `sega frontend down`

Stop frontend servers for projects in a group.

```bash
sega frontend down --group GROUP [--project PROJECT]

Options:
  --group    Project group to stop (group1, group2, group3, all)
  --project  Stop specific project(s)
  --force    Force kill processes
```

### `sega frontend status`

Show status of frontend servers.

```bash
sega frontend status [--group GROUP] [--format FORMAT]

Options:
  --group   Filter by group (default: all)
  --format  Output format: table, json, simple (default: table)
```

**Output example:**
```
Frontend Status - Group 1 (prod-01)
========================================
Project      Port   Status    Health    Mode
-----------  -----  --------  --------  --------
service-a      3001   running   healthy   shared
service-b      3002   running   healthy   shared
service-c    3009   running   healthy   shared
service-d    3004   running   healthy   shared
service-e         3005   running   healthy   shared
service-f      3006   running   healthy   shared
service-g     3007   running   healthy   shared
service-h        3019   running   healthy   shared
```

### `sega frontend install`

Install/sync dependencies for shared mode.

```bash
sega frontend install [--mode MODE] [--update]

Options:
  --mode    Target mode: shared or isolated
  --update  Update dependencies (npm update)
```

## Port Allocation

**Authoritative Source**: [PORT_ALLOCATION_STANDARDS.md](/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md)

Standard ports follow formula: `Landing=3000+offset`, `API=8000+offset`

| Project | Landing Port | API Port | Offset |
|---------|--------------|----------|--------|
| service-g | 3000 | 8000 | 0 |
| service-e | 3002 | 8002 | 2 |
| service-a | 3003 | 8003 | 3 |
| service-b | 3008 | 8008 | 8 |
| service-c | 3009 | 8009 | 9 |
| service-d | 3011 | 8011 | 11 |
| service-f | 3012 | 8012 | 12 |
| service-p | 3016 | 8016 | 16 |
| service-q | 3017 | 8017 | 17 |
| service-h | 3019 | 8019 | 19 |

See [URL_AND_ADDRESSING_REGISTRY.md](/docs/standards/infrastructure/URL_AND_ADDRESSING_REGISTRY.md) for complete URL reference.

## Workflows

### Development Workflow (Local)

```bash
# 1. Ensure shared dependencies are installed
sega frontend install --mode shared

# 2. Start development servers
sega frontend up --group group1 --mode shared --dev

# 3. Check status
sega frontend status

# 4. Stop when done
sega frontend down --group group1
```

### Production Deployment (EC2)

```bash
# 1. SSH to instance
ssh -i ~/example-prod.pem ubuntu@203.0.113.10

# 2. Pull latest code
cd ~/portfolio && git pull

# 3. Build with isolated dependencies for production
sega frontend build --group group1 --mode isolated --clean

# 4. Start production servers
sega frontend serve --group group1 --background

# 5. Verify with nginx
curl -I http://localhost:3001
```

### CI/CD Integration

```yaml
# .gitlab-ci.yml example
deploy_frontends:
  stage: deploy
  script:
    - sega frontend build --group group1 --mode isolated --clean
    - sega frontend serve --group group1 --background
    - sega frontend status --format json > frontend-status.json
  artifacts:
    paths:
      - frontend-status.json
```

## Configuration

Configuration in `/sega/config/unified_server.yaml`:

```yaml
frontend_orchestration:
  default_mode: "shared"

  build:
    command: "npm run build"
    output_dir: ".next"
    timeout: 300

  serve:
    command: "npm run start"
    dev_command: "npm run dev"
    health_check_path: "/"
    startup_timeout: 30

  parallel:
    max_concurrent: 4
    stagger_delay: 2
```

## Troubleshooting

### Build Failures

```bash
# Check build logs
sega frontend build --group group1 --project service-c 2>&1 | tee build.log

# Clean and rebuild
sega frontend build --group group1 --clean

# Try isolated mode if shared has conflicts
sega frontend build --group group1 --mode isolated
```

### Port Conflicts

```bash
# Check what's using a port
lsof -i :3001

# Kill process on port
kill $(lsof -t -i:3001)

# Or use sega frontend down
sega frontend down --group group1 --force
```

### Dependency Issues in Shared Mode

```bash
# Reinstall shared dependencies
cd ~/portfolio/environments
rm -rf node_modules
npm install

# Or use sega
sega frontend install --mode shared --update
```

## Relationship with Docker Compose

SEGA's `frontend` command provides an alternative to Docker Compose for frontend orchestration, optimized for development workflows.

### When to Use Each Approach

| Scenario | Recommended | Why |
|----------|-------------|-----|
| Local development | `sega frontend` | Faster iteration with shared deps |
| CI/CD pipeline | `docker compose` | Isolated, reproducible builds |
| Production deployment | `docker compose` | Full isolation, prod-like environment |
| Multi-project testing | `sega frontend` | Efficient resource usage |
| Single project testing | Either | Both work well |

### Key Differences

| Aspect | SEGA Frontend | Docker Compose |
|--------|---------------|----------------|
| **Dependencies** | Shared (symlinked) | Isolated (per container) |
| **Install time** | ~15 min (once) | ~5 min per project |
| **Disk usage** | 8.5GB shared | ~2GB per project |
| **Process model** | 2 processes (landing + product) | 1 container (nginx routes) |
| **Hot reload** | Native Next.js dev | Requires volume mounts |

### Docker Compose Alternative

For Docker-based deployments, see the single Dockerfile pattern in:
- **[UIX_SPLIT_ROUTING_ARCHITECTURE.md](/docs/templates/web/react/guides/UIX_SPLIT_ROUTING_ARCHITECTURE.md)** - Single Dockerfile configuration

This approach uses a multi-stage Dockerfile to build both `landing_app` and `product_app`, with nginx routing internally:

```yaml
# Simplified docker-compose.yml
services:
  web-app-frontend:
    build: ./frontend
    ports:
      - "3001:80"   # Single port, nginx routes internally
```

---

## Related Documentation

- **[PORT_ALLOCATION_STANDARDS.md](/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md)** - Port assignments
- **[NGINX_CONFIGURATION_STANDARDS.md](/docs/standards/deployment/NGINX_CONFIGURATION_STANDARDS.md)** - Nginx setup
- **[UNIFIED_SERVER_DEPLOYMENT.md](/sega/docs/deployment/UNIFIED_SERVER_DEPLOYMENT.md)** - Unified server commands
- **[UIX_SPLIT_ROUTING_ARCHITECTURE.md](/docs/templates/web/react/guides/UIX_SPLIT_ROUTING_ARCHITECTURE.md)** - Docker Compose patterns
- **[shared-node-modules.md](/sega/docs/setup/shared-node-modules.md)** - Shared dependencies (SEGA-only)
- **[FRONTEND_TESTING_MODES.md](/docs/standards/infrastructure/FRONTEND_TESTING_MODES.md)** - Consolidated testing modes guide

---

**File Reference**: `/sega/docs/reference/frontend-orchestration.md`
