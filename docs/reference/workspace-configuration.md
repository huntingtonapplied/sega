# SEGA Generic Usage Guide

## Overview

SEGA is now fully configurable and can be used with any workspace for monorepo. This guide shows how to use SEGA'as local deployment features with your own projects.

## Quick Start

### . Install SEGA

```bash
pip install sega
```

Or clone and install from source:
```bash
git clone https://github.com/yourepo/sega.git
cd sega
pip install -e .
```

### . Create Configuration file

Create a `.sega.yml` file in your workspace root:

```yaml
workspace:
  name: "My Project"
  compose_project_prefix: "myproject"
  
project_discovery:
  scan_paths:
    - "."
  exclude_paths:
    - ".git"
    - "node_modules"
  project_markers:
    - "docker-compose.yml"
    
environment_defaults:
  NOD_NV: "development"
  NV: "development"
```

### . Use SEGA Commands

**Core Principle**: Actions are commands, platforms are options.

```bash
# List available projects
sega local list

# Start all projects
sega local up --all

# Start specific projects
sega local up -p frontend -p backend

# Check status
sega local status

# View logs
sega local logs frontend

# Stop everything
sega local down --all

# Build & Package (sega forge)
sega forge build --platform web       # Build frontend
sega forge build --platform desktop   # Build Electron app
sega forge publish --target registry  # Push to container registry

# Testing (sega probe)
sega probe run                        # Auto-detect and run tests
sega probe run --type unit            # Unit tests only
sega probe browser --visual           # Visual regression testing

# Deployment (sega ship)
sega ship deploy --target staging
sega ship deploy --target production
sega ship rollback --steps 1

# Diagnostics (sega doctor)
sega doctor check                     # Quick health check
sega doctor repair                    # Auto-fix issues
```

See [CLI Reference](../reference/cli-reference.md) for complete command documentation.

## Configuration Options

### Minimal Configuration

for simple projects with docker-compose files:

```yaml
workspace:
  name: "Simple pp"
  compose_project_prefix: "simpleapp"
```

### ull Configuration

for complex workspaces with shared infrastructure:

```yaml
workspace:
  name: "nterprise pp"
  organization: "My Company"
  root: "."
  compose_project_prefix: "enterprise"
  
# Shared infrastructure (databases, caches)
infrastructure:
  compose_file: "infrastructure/docker-compose.yml"
  profiles:
    development:
      postgres:
        port: 5
        database: "app_dev"
        user: "appuser"
        password: "devpass"
      redis:
        port: 
    testing:
      postgres:
        port: 5
        database: "app_test"
        user: "testuser"
        password: "testpass"
      redis:
        port: 
  management_tools:
    pgadmin:
      port: 55
      email: "admin@mycompany.com"
      password: "admin"
    redis_commander:
      port: 

# How to find projects
project_discovery:
  scan_paths:
    - "services"
    - "apps"
  exclude_paths:
    - ".git"
    - "node_modules"
    - "__pycache__"
    - "vendor"
  project_markers:
    - "docker-compose.yml"
    - "docker-compose.dev.yml"
  compose_file_patterns:
    - "docker-compose.dev.yml"
    - "docker-compose.yml"
    - "deployment/docker-compose.yml"

# Project-specific settings
projects:
  frontend:
    compose_file: "docker-compose.yml"
    environment:
      RCT_PP_PI_URL: "http://localhost:"
  
  backend:
    has_makefile: true
    compose_file: "docker-compose.yml"
    environment:
      DTS_URL: "postgresql://appuser:devpass@localhost:5/app_dev"

# Default environment variables
environment_defaults:
  NOD_NV: "development"
  NV: "development"
  LOG_LVL: "debug"

# Development setup
development:
  shared_venv:
    path: ".venv"
    setup_script: "scripts/setup.sh"

# Deployment behavior
deployment:
  prefer_makefile: true
  makefile_targets:
    up: ["up", "start", "dev"]
    down: ["down", "stop"]
  health_check:
    enabled: true
    timeout: 
```

## Project Discovery

SEGA automatically discovers projects based on your configuration:

. **Scan Paths**: Directories to search for projects
. **xclude Paths**: Directories to skip
. **Project Markers**: files that indicate a deployable project
. **Compose file Patterns**: Where to look for docker-compose files

## Makefile Integration

If your project has a Makefile, SEGA will try to use it first:

```makefile
# Makefile
up:
	docker-compose up -d

down:
	docker-compose down

start: up
stop: down
```

Configure which targets SEGA should try:

```yaml
deployment:
  prefer_makefile: true
  makefile_targets:
    up: ["up", "start", "dev", "run"]
    down: ["down", "stop", "halt"]
```

## Environment Variables

SEGA manages environment variables in three ways:

. **Environment Defaults**: pplied to all projects
. **Project-Specific Environment**: Per-project variables
. **xisting .env files**: Preserved and enhanced

example generated .env file:
```env
# uto-generated environment file for frontend
NOD_NV=development
NV=development
LOG_LVL=debug
RCT_PP_PI_URL=http://localhost:
DTS_HOST=enterprise_dev_postgres
DTS_PORT=5
DTS_NM=frontend_dev
DTS_USR=appuser
DTS_PSSWORD=devpass
RDIS_HOST=enterprise_dev_redis
RDIS_PORT=
```

## Shared Infrastructure

Configure shared databases and caches that all projects can use:

```yaml
infrastructure:
  compose_file: "infrastructure/docker-compose.yml"
  profiles:
    development:
      postgres:
        port: 5
        database: "shared_dev"
        user: "shareduser"
        password: "sharedpass"
      redis:
        port: 
```

Your infrastructure docker-compose.yml should define services with matching profiles:

```yaml
version: '.'

services:
  postgres:
    image: postgres:
    profiles: ["development", "all"]
    environment:
      POSTGRS_D: shared_dev
      POSTGRS_USR: shareduser
      POSTGRS_PSSWORD: sharedpass
    ports:
      - "5:5"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:
    profiles: ["development", "all"]
    ports:
      - ":"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## Multiple Workspaces

You can have different configurations for different contexts:

```bash
# Development
sega local --config .sega.dev.yml up --all

# Staging
sega local --config .sega.staging.yml up --all

# Testing
sega local --config .sega.test.yml up --all
```

## CI/CD Integration

Use SEGA in your CI/CD pipelines:

```yaml
# .github/workflows/test.yml
name: Test
on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v
      
      - name: Setup Python
        uses: actions/setup-python@v
        with:
          python-version: '.'
          
      - name: Install SEGA
        run: pip install sega
        
      - name: Start services
        run: sega local up --all
        
      - name: Run tests
        run: |
          sega local status
          npm test
          
      - name: Stop services
        run: sega local down --all
```

## Troubleshooting

### No Projects found

Check your configuration:
```bash
# Debug project discovery
sega local list

# Check your scan paths and markers
cat .sega.yml
```

### Docker Issues

```bash
# Check Docker is running
docker ps

# Clean up Docker
docker system prune -a

# Check SEGA'as Docker client
sega local status --infra
```

### Configuration Not found

SEGA searches for configuration in this order:
. `--config` command line option
. `.sega.yml` in current directory
. `sega.yml` in current directory
. Parent directories up to home

### Port Conflicts

Update your configuration to use different ports:
```yaml
infrastructure:
  profiles:
    development:
      postgres:
        port: 5  # Changed from 5
      redis:
        port:   # Changed from 
```

## xamples

### Node.js Microservices

```yaml
workspace:
  name: "Microservices"
  compose_project_prefix: "micro"
  
project_discovery:
  scan_paths:
    - "services"
  project_markers:
    - "package.json"
    - "docker-compose.yml"
    
environment_defaults:
  NOD_NV: "development"
  PORT: ""
```

### Python Monorepo

```yaml
workspace:
  name: "Python Monorepo"
  compose_project_prefix: "pyapp"
  
project_discovery:
  scan_paths:
    - "apps"
    - "libs"
  project_markers:
    - "pyproject.toml"
    - "docker-compose.yml"
    
development:
  shared_venv:
    path: ".venv"
    setup_script: "scripts/setup-venv.sh"
```

### ull Stack Application

```yaml
workspace:
  name: "ull Stack pp"
  compose_project_prefix: "fullstack"
  
projects:
  frontend:
    compose_file: "frontend/docker-compose.yml"
    environment:
      VIT_PI_URL: "http://localhost:"
      
  backend:
    compose_file: "backend/docker-compose.yml"
    has_makefile: true
    environment:
      DTS_URL: "postgresql://user:pass@postgres:5/db"
      
  nginx:
    compose_file: "nginx/docker-compose.yml"
```

## Migration from Scripts

If you'are migrating from shell scripts:

. Create `.sega.yml` configuration
. Replace script commands:
   - `./deploy.sh` → `sega local up --all`
   - `./stop.sh` → `sega local down --all`
   - `./logs.sh app` → `sega local logs app`
   - `./status.sh` → `sega local status`
. Remove old scripts
. Update documentation

## Project Onboarding

### Adding New Projects to SEGA

**Phase 1: Detection**
```bash
cd /path/to/new-project
sega detect                    # Verify project type detection
sega doctor check              # Ensure environment ready
```

**Phase 2: Configuration**
```bash
sega init                      # Generate sega.yaml
sega secrets verify            # Check required secrets
```

**Example sega.yaml:**
```yaml
project:
  name: "my-project"
  type: "web_app"
  version: "1.0.0"

build:
  dockerfile: "Dockerfile"

deployment:
  staging:
    replicas: 2
  production:
    replicas: 3
```

**Phase 3: Integration Testing**
```bash
sega forge build --platform web --dry-run     # Test build
sega ship deploy --target staging --dry-run   # Test deployment
sega probe run                                # Run tests
```

**Phase 4: CI/CD Integration**
```yaml
# .gitlab-ci.yml
build:
  script:
    - sega forge build --platform web
deploy:staging:
  script:
    - sega ship deploy --target staging
```

### Validation Checklist

- [ ] `sega detect` identifies project type correctly
- [ ] `sega init` generates valid configuration
- [ ] `sega forge build --dry-run` succeeds
- [ ] `sega ship deploy --dry-run` succeeds
- [ ] `sega probe run` passes tests

---

## Contributing

SEGA is open source and welcomes contributions. To add support for your stack:

. ork the repository
. dd your detection patterns
. Submit a pull request

for more information, see the [contribution guide](CONTRIUTING.md).