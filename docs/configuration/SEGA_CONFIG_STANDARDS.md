# SEGA Configuration Standards

## Overview
SEGA uses a dual configuration system with both files and directories serving specific purposes across the portfolio.

## Configuration Types

### 1. Project Configuration Files

#### Current Standard: `sega.yaml`
- **Purpose**: Main project configuration file
- **Location**: Project root directory
- **Status**: PREFERRED - All new projects should use this format
- **Example Projects**: api-service, web-app, service-a, service-b, service-c, example-project

#### Legacy Format: `.sega.yml`
- **Purpose**: Legacy project configuration (being phased out)
- **Location**: Project root directory
- **Status**: DEPRECATED - Still supported but should be migrated
- **Example Projects**: legacy-service-a, legacy-service-b, legacy-web-app
- **Migration**: Run `sega init` to migrate from `.sega.yml` to `sega.yaml`

### 2. Runtime Configuration Directory: `.sega/`

#### Purpose
The `.sega/` directory stores runtime configuration and test data that should NOT be committed to version control.

#### Contents
- `laboratory_config.yaml`: Test environment configuration
- `test-config.yml`: Test runner configuration
- `benchmark_results.json`: Performance benchmark results
- `test-results/`: Test execution results
- `terraform/`: Terraform state files (local deployments)
- `error_history.json`: Error tracking history

#### Location
- Project-specific: `<project>/.sega/`
- User home: `~/.sega/` (for global settings)

## Configuration Hierarchy

```
project/
├── sega.yaml              # Main project config (committed)
├── .sega.yml              # Legacy config (migrate to sega.yaml)
└── .sega/                 # Runtime directory (gitignored)
    ├── laboratory_config.yaml
    ├── test-config.yml
    ├── benchmark_results.json
    └── test-results/
```

## Detection Logic

SEGA's project detector follows this precedence:

1. **Check for `sega.yaml`** (new standard)
2. **Fallback to `.sega.yml`** (legacy support)
3. **Check `.sega/` directory** for runtime configs (test environments)

## Best Practices

### DO:
- ✅ Use `sega.yaml` for all new projects
- ✅ Commit `sega.yaml` to version control
- ✅ Add `.sega/` to `.gitignore`
- ✅ Store sensitive test configs in `.sega/` directory
- ✅ Migrate legacy `.sega.yml` files to `sega.yaml`

### DON'T:
- ❌ Commit `.sega/` directory contents
- ❌ Create new `.sega.yml` files (use `sega.yaml`)
- ❌ Mix configuration between files and directories
- ❌ Store production secrets in any configuration file

## Migration Guide

### From `.sega.yml` to `sega.yaml`

1. **Automatic migration**:
   ```bash
   sega init --migrate
   ```

2. **Manual migration**:
   ```bash
   mv .sega.yml sega.yaml
   git add sega.yaml
   git rm .sega.yml
   git commit -m "Migrate from .sega.yml to sega.yaml"
   ```

## Configuration File Structure

### `sega.yaml` Schema

```yaml
# Project metadata
project:
  name: "project-name"
  type: "web|mobile|desktop|embedded|hardware"
  version: "1.0.0"

# Component configuration
components:
  frontend:
    framework: "react|vue|angular"
    port: 3000
  backend:
    framework: "fastapi|django|express"
    port: 8000
  database:
    type: "postgresql|mysql|mongodb"
    port: 5432

# Testing configuration
testing:
  framework: "pytest|jest|cargo"
  coverage_threshold: 80

# Deployment configuration
deployment:
  environments:
    - development
    - staging
    - production
  strategy: "docker|kubernetes|ansible|terraform"
```

## Runtime Directory Structure

### `.sega/` Contents

```yaml
# laboratory_config.yaml - Test environment settings
test_environment:
  database_url: "postgresql://test:test@localhost:5432/test_db"
  redis_url: "redis://localhost:6379"
  api_base_url: "http://localhost:8000"

# test-config.yml - Test runner configuration
test_runner:
  parallel: true
  timeout: 300
  retry: 2
  verbose: true
```

## Environment-Specific Behavior

### Development
- Uses `.sega/` for local test configurations
- Reads both `sega.yaml` and `.sega.yml` for compatibility

### CI/CD
- Relies on `sega.yaml` for pipeline configuration
- Generates `.sega/` directory for test artifacts

### Production
- Only uses `sega.yaml` for deployment configuration
- `.sega/` directory not used in production environments

## Troubleshooting

### Q: Should I have both `.sega.yml` and `sega.yaml`?
**A**: No, use only `sega.yaml`. If you have both, migrate to `sega.yaml` and remove `.sega.yml`.

### Q: Is the `.sega/` directory required?
**A**: No, it's created automatically when needed (during testing, benchmarking, etc.).

### Q: What if SEGA can't find my configuration?
**A**: Run `sega doctor` to diagnose configuration issues, then `sega init` to create proper configuration.

### Q: Should `.sega/` be in version control?
**A**: No, always add `.sega/` to `.gitignore`. It contains runtime and test data that shouldn't be committed.

## Summary

- **`sega.yaml`**: Main project configuration (committed, required)
- **`.sega.yml`**: Legacy configuration (deprecated, migrate to sega.yaml)
- **`.sega/`**: Runtime directory for test configs and artifacts (gitignored, optional)

Both the file and directory serve different purposes and can coexist, but only `sega.yaml` should be used for project configuration going forward.