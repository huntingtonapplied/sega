# Portfolio CI/CD Management with SEGA

This guide demonstrates how to use SEGA as a **portfolio-level CI/CD tool** for managing multiple projects across teams.

## Overview

SEGA is designed for **high-level usage** as a project portfolio management tool. It can:

- Auto-discover git projects in your workspace
- Initialize configurations across multiple projects
- Coordinate deployments across teams
- Manage project dependencies and shared resources

## Portfolio-Level Operations

### 1. Initialize Entire Portfolio

Run SEGA from your **workspace root directory** (e.g., `/portfolio/projects/`):

```bash
# Discover and initialize all git projects
sega init --portfolio

# Filter by team
sega init --portfolio --team team-a --team team-b

# Filter by project type
sega init --portfolio --project-type-filter web_app --project-type-filter ml_pipeline

# Dry run to see what would be done
sega init --portfolio --dry-run
```

**What this does:**
- Scans directory tree for `.git` repositories
- Auto-detects project types for each repository
- Extracts team names from directory structure
- Generates minimal `sega.yaml` for each project
- Creates `.gitlab-ci.yml` for each project
- Generates health endpoint templates for web/ML projects
- Creates workspace configuration files

### 2. Workspace Configuration Files

After portfolio initialization, you'All have:

```
/portfolio/projects/
 sega-workspace.yaml      # Complete workspace configuration
 sega-projects.yaml       # Project paths organized by team
 team-a/
    web-app/
       sega.yaml        # Auto-generated config
       .gitlab-ci.yml   # Auto-generated CI/CD
       health.py        # Health endpoint template
    api-service/
        sega.yaml
        .gitlab-ci.yml
 team-b/
     edge-device/
         sega.yaml
         .gitlab-ci.yml
```

### 3. Project Path Loading

SEGA supports loading project paths from configuration:

```yaml
# sega-projects.yaml (auto-generated)
projects:
  team-a:
    - "team-a/web-app"
    - "team-a/api-service"
  team-b:
    - "team-b/edge-device"
  team-c:
    - "team-c/sega"
    - "team-c/ml-service"
```

## Git Auto-Detection

SEGA automatically discovers projects by:

1. **Walking directory tree** from current location
2. **Finding `.git` repositories** (skips hidden dirs, environments/node_modules, etc.)
3. **Extracting project metadata**:
   - Team name from directory structure
   - Project name from repository folder
   - Git URL from remote origin
   - Current branch and last commit
   - Project type via auto-detection

### Example Discovery Output

```bash
$ sega init --portfolio --dry-run

 Discovering git projects in portfolio...
 Found 12 git projects

 Portfolio Summary:
   Total projects: 12
   With SEGA config: 3
   By team:
     team-a: 3 projects
     team-b: 1 projects
     team-c: 4 projects
     team-d: 2 projects
     team-e: 2 projects
   By type:
     web_app: 6 projects
     ml_pipeline: 2 projects
     hybrid_system: 2 projects
     firmware_edge: 1 projects
     native_app: 1 projects

 Dry run - would initialize:
   team-a/web-app (web_app) -  would create
   team-a/api-service (web_app) -  has config
   team-b/edge-device (hybrid_system) -  would create
   team-c/ml-service (ml_pipeline) -  would create
   ...
```

## Minimal Working Configuration

SEGA generates **minimal working configurations** that actually get processed:

```yaml
# sega.yaml (auto-generated)
version: "2.1"
project:
  name: "web-app"
  type: "web_app"
  domain: "example"
  team: "team-a"

# Multi-component support (for hybrid systems)
components:
  - name: "frontend"
    type: "web_app"
    path: "./frontend"
  - name: "backend"
    type: "web_app"
    path: "./backend"

# Deployment configuration
deployment:
  targets:
    staging:
      type: "aws-ecs"
      region: "us-east-1"
      cluster: "staging-cluster"
      strategy: "rolling"
      auto_deploy: true
      infrastructure:
        port: 3000
        health_check_path: "/health"
        cpu: 256
        memory: 512
        min_instances: 2
        max_instances: 10
    production:
      type: "aws-ecs"
      region: "us-east-1"
      cluster: "production-cluster"
      strategy: "canary"
      auto_deploy: false
      approval_required: true
      infrastructure:
        port: 3000
        health_check_path: "/health"
        cpu: 256
        memory: 512
        min_instances: 2
        max_instances: 10

# Build configuration
build:
  strategy: "containerized"
  docker:
    dockerfile: "Dockerfile"
    context: "."
    registry: "ecr"
```

## GitLab CI/CD Integration

Auto-generated `.gitlab-ci.yml` for each project:

```yaml
# Auto-generated GitLab CI for a portfolio project
# Team: team-a, Project: web-app, Type: web_app

include:
  - project: 'my-org/sega'
    file: '/templates/default/gitlab-ci.yml'

variables:
  SEGA_TEAM: "team-a"
  SEGA_PROJECT: "web-app"
  SEGA_PROJECT_TYPE: "web_app"

stages:
  - validate
  - build
  - test
  - security
  - deploy-staging
  - deploy-production
```

## Portfolio Deployment

After initialization, you can deploy across the portfolio:

```bash
# Deploy entire team
sega workspace deploy --team team-a --target staging

# Deploy specific projects (use multiple --project flags)
sega workspace deploy --project team-a/web-app --project team-b/edge-device --target production

# Deploy with different strategies
sega workspace deploy --team team-a --target staging --strategy parallel
sega workspace deploy --team team-a --target staging --strategy coordinated
sega workspace deploy --team team-a --target staging --strategy fail_fast
```

## Workspace Commands

### List Projects

```bash
# List all projects
sega workspace list

# Filter by team
sega workspace list --team team-a

# Filter by type
sega workspace list --type web_app

# Load from custom configuration
sega workspace list --config custom-projects.yaml

# Output in different formats
sega workspace list --format json
sega workspace list --format yaml
```

### Validate Workspace

```bash
# Validate all project configurations
sega workspace validate

# Check dependencies
sega workspace dependencies

# Show shared resources
sega workspace shared
```

### Generate Configuration

```bash
# Generate workspace configuration
sega workspace config --output workspace-config.yaml
```

## Project Requirements

For optimal SEGA portfolio management, projects should have:

### 1. Git Repository
- Must be a valid git repository
- Should have remote origin configured
- Follow the standard directory structure: `team/project/`

### 2. Project Structure
```
project/
 .git/
 Dockerfile              # For containerized deployment
 health.py/.js           # Health endpoint (auto-generated)
 sega.yaml              # SEGA configuration (auto-generated)
 .gitlab-ci.yml         # GitLab CI (auto-generated)
 project-specific-files/
```

### 3. Health Endpoint
SEGA auto-generates health endpoints for web/ML projects:

**For Node.js projects (if package.json exists):**
```javascript
// health.js (auto-generated)
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: process.env.SEGA_PROJECT || 'unknown'
  });
});
```

**For Python projects (if requirements.txt exists):**
```python
# health.py (auto-generated)
@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': os.getenv('SEGA_PROJECT', 'unknown')
    })
```

### 4. Dockerfile
Each project should have a Dockerfile that:
- Exposes the correct port (3000 for web, 8000 for ML)
- Includes the health endpoint
- Sets proper environment variables

## Advanced Features

### 1. Selective Initialization
```bash
# Initialize only web aApplications
sega init --portfolio --project-type-filter web_app

# Initialize only specific teams
sega init --portfolio --team team-a --team team-b

# Initialize projects without existing config
sega init --portfolio --force

# Use custom template
sega init --portfolio
```

### 2. Custom Configuration Loading
```bash
# Load projects from custom configuration
sega workspace list --config my-projects.yaml

# Save current workspace configuration
sega workspace config --output my-workspace.yaml
```

### 3. Workspace Validation
```bash
# Validate all project configurations
sega workspace validate

# Check dependencies
sega workspace dependencies --format json

# Show shared resources
sega workspace shared --format yaml
```

### 4. Team Operations
```bash
# View team-specific projects
sega workspace team team-a

# Deploy entire team
sega workspace deploy --team team-a --target staging
```

## Best Practices

### 1. Directory Structure
```
/portfolio/projects/              # Workspace root
 team-a/              # Team directory
    web-app/             # Project directory
    api-service/
 team-b/
    edge-device/
 team-c/
     sega/              # SEGA platform itself
     ml-service/
```

### 2. Team Organization
- Use consistent team directory naming
- Keep related projects under team directories
- Use descriptive project names

### 3. Configuration Management
- Run `sega init --portfolio` from workspace root (`/portfolio/projects/`)
- Use `--dry-run` to preview changes
- Commit generated configurations to git
- Use `--force` to update existing configurations

### 4. GitLab CI Integration
- Include SEGA templates in your GitLab instance
- Set up proper CI/CD variables
- Use team-specific runners if needed

## Deployment Strategies

### Coordinated Strategy (Default)
- Respects all dependencies
- Sequential execution with parallelism where possible
- Automatic rollback on failure

### Parallel Strategy
- Maximum parallelism within constraints
- Resource-aware scheduling
- Parallel health checks

### Fail-Fast Strategy
- Stops on first failure
- Immediate rollback
- Detailed error reporting

## Configuration File Examples

### Custom Project Configuration
```yaml
# custom-projects.yaml
projects:
  team-a:
    - "team-a/web-app"
    - "team-a/api-service"
  team-b:
    - "team-b/edge-device"
metadata:
  created_by: "sega init --portfolio"
  last_updated: "2024-07-16"
```

### Workspace Configuration
```yaml
# sega-workspace.yaml (auto-generated)
version: "2.1"
workspace:
  root_path: "/portfolio/projects"
  total_projects: 12
  teams:
    team-a: ["team-a/web-app", "team-a/api-service"]
    team-b: ["team-b/edge-device"]
  projects:
    "team-a/web-app":
      name: "web-app"
      team: "team-a"
      type: "web_app"
      path: "team-a/web-app"
      has_sega_config: true
```

## Troubleshooting

### Common Issues

1. **No git projects found**
   - Ensure you'are in the correct directory (`/portfolio/projects/`)
   - Check that subdirectories have `.git` folders
   - Verify directory permissions

2. **Team detection fails**
   - Ensure directory structure follows `team/project/` pattern
   - Check that parent directories exist

3. **Project type detection fails**
   - Ensure projects have recognizable files (package.json, requirements.txt, etc.)
   - Use `--type` option to override detection

4. **Health endpoint not generated**
   - Ensure Node.js projects have `package.json`
   - Ensure Python projects have `requirements.txt`
   - Other languages need manual health endpoint creation

5. **Workspace deployment fails**
   - Check that all projects have valid `sega.yaml` configurations
   - Verify AWS credentials and permissions
   - Use `--dry-run` to test deployment plan

### Getting Help

```bash
# Show portfolio status
sega workspace list

# Validate configuration
sega workspace validate

# Show dependency graph
sega workspace dependencies

# Get detailed project info
sega detect --verbose

# Test single project deployment
sega deploy --target staging --dry-run
```

### Error Resolution

If you encounter errors:

1. **Run validation first**: `sega workspace validate`
2. **Check individual projects**: `cd project && sega doctor`
3. **Use dry-run mode**: `sega workspace deploy --dry-run --target staging`
4. **Check logs**: Look at deployment logs for specific error messages
5. **Rollback if needed**: `sega workspace rollback --target staging`

This portfolio-level approach allows SEGA to scale across large organizations while maintaining simplicity for individual projects.