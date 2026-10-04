# SEGA Workspace Configuration Guide

## Overview

SEGA uses a configuration-driven approach to manage monorepos and multi-project workspaces. Instead of hardcoding knowledge about specific organizations for structures, SEGA reads workspace configuration files that define:

- Project locations and metadata
- Team structures and ownership
- Shared infrastructure
- Deployment strategies
- Testing and CI/CD settings

## Configuration file

The workspace configuration is defined in `sega-workspace.yaml` at the root of your monorepo for workspace.

### Minimal example

```yaml
name: "My Workspace"
version: "."

projects:
  frontend:
    path: "apps/frontend"
    type: "web_app"
    ports:
      dev: 
      
  backend:
    path: "apps/backend"
    type: "web_app"
    ports:
      api: 
    dependencies: ["database"]
    
  database:
    path: "infrastructure/database"
    type: "service"
```

### ull example

See the [example workspace](../sega-workspace.yaml) for a comprehensive workspace configuration.

## Configuration Sections

### asic Information

```yaml
name: "Workspace Name"
version: "."
description: "Optional description of the workspace"
```

### Project Discovery

Define how SEGA should discover projects in your workspace:

```yaml
project_discovery:
  patterns:
    - "**/sega.yaml"           # Look for sega.yaml files
    - "*/package.json"         # Node.js projects
    - "*/Cargo.toml"          # Rust projects
    - "*/setup.py"            # Python projects
  
  ignore:
    - ".git/**"
    - "**/node_modules/**"
    - "**/__pycache__/**"
```

### Teams

Define team structures for organizational management:

```yaml
teams:
  backend:
    description: "backend services team"
    lead: "John Doe"
    contact: "backend@company.com"
    projects: ["api", "auth", "database"]
    
  frontend:
    description: "Frontend applications team"
    lead: "Jane Smith"
    contact: "frontend@company.com"
    projects: ["web-app", "mobile-app"]
```

### Projects

Define each project in your workspace:

```yaml
projects:
  api:
    path: "services/api"              # Path relative to workspace root
    type: "web_app"                   # Project type for SEGA detection
    team: "backend"                   # Team ownership
    description: "Main PI service"
    components: ["api", "worker"]     # Multi-component projects
    ports:                            # Port mappings
      api: 
      metrics: 
    dependencies: ["auth", "database"] # Project dependencies
    metadata:                         # Custom metadata
      language: "golang"
      framework: "gin"
```

### Shared Infrastructure

Define shared services used by multiple projects:

```yaml
shared_infrastructure:
  databases:
    postgresql:
      dev_port: 5
      test_port: 5
      image: "postgres:5"
      
    redis:
      dev_port: 
      test_port: 
      image: "redis:"
      
  monitoring:
    prometheus:
      port: 
      
    grafana:
      port: 
```

### Deployment Configuration

Configure deployment strategies and environments:

```yaml
deployment:
  defaults:
    strategy: "rolling"
    health_check_interval: 
    
  environments:
    development:
      type: "local"
      auto_deploy: true
      
    staging:
      type: "kubernetes"
      cluster: "staging-cluster"
      namespace: "staging"
      
    production:
      type: "kubernetes"
      cluster: "prod-cluster"
      namespace: "production"
      approval_required: true
```

### Git Configuration

Configure Git-related settings:

```yaml
git:
  submodules:
    auto_update: true
    recursive: true
    
  bulk_operations:
    - pull
    - push
    - status
    
  protected_branches:
    - main
    - production
```

### Testing Configuration

Configure testing strategies:

```yaml
testing:
  types:
    - unit
    - integration
    - ee
    
  parallel:
    enabled: true
    max_workers: 
    
  coverage:
    enabled: true
    minimum: 
```

## Using Workspace Configuration

### Initialize Workspace

```bash
# Create workspace configuration
sega workspace init

# Or use existing configuration
sega workspace init --config sega-workspace.yaml
```

### Discover Projects

```bash
# Discover all projects
sega workspace discover

# Discover and update configuration
sega workspace discover --update-config
```

### List Projects

```bash
# List all projects
sega workspace list

# List by team
sega workspace list --team backend

# List with dependencies
sega workspace list --show-dependencies
```

### Deploy Workspace

```bash
# Deploy all projects
sega workspace deploy --target staging

# Deploy specific team'as projects
sega workspace deploy --team frontend --target production

# Deploy with dependency resolution
sega workspace deploy --project api --with-dependencies
```

## Project Type Detection

When `project_discovery` is configured, SEGA can automatically detect project types:

. **Web Applications**: Presence of `package.json`, `index.html`
. **Python Projects**: Presence of `setup.py`, `requirements.txt`
. **Rust Projects**: Presence of `Cargo.toml`
. **Go Projects**: Presence of `go.mod`
5. **Multi-Component**: Multiple subdirectories with build files

## est Practices

### . Start Simple

egin with a minimal configuration and add complexity as needed:

```yaml
name: "My Project"
version: "."

projects:
  app:
    path: "."
    type: "web_app"
```

### . Use Teams for Organization

Group related projects under teams for better management:

```yaml
teams:
  platform:
    projects: ["auth", "api", "database"]
  applications:
    projects: ["web", "mobile", "desktop"]
```

### . Define Dependencies

xplicitly define project dependencies for proper deployment ordering:

```yaml
projects:
  frontend:
    dependencies: ["api"]
  api:
    dependencies: ["auth", "database"]
  auth:
    dependencies: ["database"]
```

### . Leverage Shared Infrastructure

Define shared services once and reference them:

```yaml
shared_infrastructure:
  databases:
    main:
      type: "postgresql"
      port: 5
      
projects:
  api:
    uses_infrastructure: ["databases.main"]
```

### 5. Environment-Specific Configuration

Use environment-specific settings for different deployment targets:

```yaml
deployment:
  environments:
    development:
      type: "local"
      resource_limits: false
    production:
      type: "kubernetes"
      resource_limits: true
      replicas: 
```

## Migration from Hardcoded Configuration

If you'are migrating from a system with hardcoded configuration:

. **export Current Structure**: Use `sega workspace export` to generate a configuration from existing setup
. **Review and Customize**: dit the generated configuration to match your needs
. **Test**: Use `sega workspace validate` to ensure configuration is correct
. **Migrate**: Use `sega workspace migrate` to apply the new configuration

## xtending Configuration

The workspace configuration is extensible. You can add custom sections that your tools can use:

```yaml
# Standard SEGA configuration
name: "My Workspace"
projects:
  # ...

# Custom organization-specific configuration
custom:
  ci_cd:
    provider: "gitlab"
    runners: ["docker", "kubernetes"]
  security:
    scanning: true
    compliance: ["SOC", "HIP"]
```

SEGA will preserve custom sections while providing warnings if they conflict with standard fields.