# SEGA Deployment Architecture
<!-- Type: Reference Document -->

## Overview

SEGA manages local deployment for a monorepo with three distinct modes, each serving different development needs. This document defines the authoritative deployment architecture.

## Core Principles

1. **SEGA manages everything** - Single source of truth for environment configuration
2. **No shared databases** - Each project owns its runtime services
3. **Shared development dependencies only** - Venv and node_modules are shared
4. **Three distinct deployment modes** - Clear separation of concerns

## Deployment Modes

### 1. Docker Mode: `sega local up`
- **Purpose**: Production-like testing environment
- **Implementation**: Uses `make up` or `make start` targets
- **Result**: Everything runs in Docker containers
- **Use case**: Testing deployment, integration testing

### 2. Development Mode: `sega local dev`
- **Purpose**: Pure local development without containers
- **Implementation**: Uses `make dev` target
- **Result**: Direct execution, no Docker overhead
- **Use case**: Fastest iteration when you manage databases manually

### 3. Hybrid Mode: `sega local hybrid`
- **Purpose**: Best development experience
- **Implementation**: Uses `make dev-shared` target
- **Process**:
  1. Start database containers (PostgreSQL, Redis, TimescaleDB)
  2. Auto-discover or create shared dependencies
  3. Execute: `make dev-shared VENV_PATH=... NODE_PATH=...`
- **Result**: Real databases + hot-reload aApplications
- **Use case**: Recommended for daily development

## Shared Dependency Management

### Auto-Discovery
SEGA searches for shared dependencies in order:
1. `./.shared_deps/venv` (project-local)
2. `../.shared_deps/venv` (monorepo root)
3. `$HOME/.sega/shared/venv` (user global)
4. Creates new if not found

Same pattern for `node_modules`.

### Version Conflict Policy
- **Strict enforcement**: No version conflicts allowed
- **On conflict**: SEGA aborts with error message
- **No fallback**: No project-specific venv in shared mode
- **Rationale**: Forces version alignment across projects

## Project Requirements

### Makefile Targets
Projects must implement these standard targets:

```makefile
# Docker deployment targets
up:
    docker-compose up -d

down:
    docker-compose down

# Direct execution target
dev:
    # Run services directly (e.g., cargo watch, npm start)

# Shared dependency target (for hybrid mode)
dev-shared:
    @export VIRTUAL_ENV=$(VENV_PATH) && \
     export PATH=$(VENV_PATH)/bin:$$PATH && \
     export NODE_PATH=$(NODE_PATH) && \
     $(MAKE) dev
```

### Docker Compose Structure
- Each project owns ALL its services
- No dependencies on shared infrastructure
- Use allocated ports from `/docs/references/port-allocation.md`

### Port Allocation
Projects must use their allocated ports:
- Frontend: 3xxx range
- Backend API: 8xxx range  
- PostgreSQL: 54xx range
- Redis: 63xx range

See `/docs/references/port-allocation.md` for specific assignments.

## Shared Infrastructure (Deprecated)

The shared infrastructure approach has been deprecated in favor of project-owned services:
- **Removed**: All database services (PostgreSQL, Redis, TimescaleDB)
- **Retained**: Development tools only
  - SSL certificate generation (if needed)
  - Package caches (if simple to implement)
  - Build caches

## Environment Variables

SEGA creates `.env` files but may not populate all required variables. Projects must document their required environment variables.

## Common Issues and Solutions

### Issue: Missing environment variables
**Solution**: Document required vars in project README

### Issue: Port conflicts
**Solution**: Use allocated ports from port allocation guide

### Issue: Version conflicts in shared dependencies
**Solution**: Align package versions across projects

### Issue: Docker not starting
**Solution**: Ensure docker-compose.yml is valid and Dockerfiles exist

## Implementation Checklist for Projects

- [ ] Implement `make up` and `make down` targets
- [ ] Implement `make dev` target for direct execution  
- [ ] Implement `make dev-shared` target for hybrid mode
- [ ] Use allocated ports from port allocation guide
- [ ] Document required environment variables
- [ ] Ensure docker-compose.yml is self-contained
- [ ] Test all three deployment modes