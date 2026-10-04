# Build Scripts Usage Guide

**Last Updated**: 2026-02-21  
**Purpose**: Clear documentation on which build scripts to use for different project types

---

## ⚠️ CRITICAL: Project Classification

A SEGA-managed ecosystem has **two types of projects** for frontend deployment purposes:

### 1. **Demo Apps** (Landing-Only)
**Definition**: Projects that ONLY have a landing page (marketing site). Product app is under development.

**Example projects**:
- atlas (landing only)
- hermes (landing only)
- orion (landing only)

**Build Script**: `build-landing-apps.sh`

### 2. **Development Apps** (Full Stack)
**Definition**: Projects that have BOTH landing_app AND product_app deployed and running.

**Example projects**:
- **atlas** (landing + product + ide)
- **hermes** (landing + product)
- **orion** (landing + product)

**Build Method**: Each project's own `docker-compose.yml` file

**Special Cases**:
- Single landing-app architecture (no product app)
- Monolithic frontend (no landing/product split)

---

## Build Script: `build-landing-apps.sh`

### Purpose
Builds **DEMO APPS ONLY** - projects that only have a landing page and are not yet full applications.

### Usage
```bash
cd ~/workspace/sega

# Build all demo apps
./scripts/build-landing-apps.sh

# Build specific demo apps
./scripts/build-landing-apps.sh atlas hermes orion
```

### What It Does
1. Installs shared `node_modules` in `~/workspace/environments/landing_app/`
2. Symlinks shared `node_modules` into each demo project
3. Builds each demo project's landing app
4. Creates Docker images and starts containers via `docker-compose.landing-apps.yml`

### ⚠️ DO NOT Use This Script For
Full-stack development apps. Use each project's own compose file instead:
- **atlas** - Use `~/workspace/atlas/docker-compose.yml`
- **hermes** - Use `~/workspace/hermes/docker-compose.yml`
- **orion** - Use `~/workspace/orion/docker-compose.yml`

---

## Development Apps: Individual Docker Compose

### Why Separate?
Development apps have multiple services:
- **landing_app**: Public marketing pages
- **product_app**: Authenticated application
- **backend/api**: Application backend
- **database**: PostgreSQL/TimescaleDB
- **redis**: Caching layer
- **workers**: Background job processors
- **Optional**: IDE, forwarders, etc.

### Building Development Apps

#### Full-Stack Example (atlas)
```bash
cd ~/workspace/atlas

# Start all services (landing + product + backend + workers + redis + ide)
docker compose up -d

# Start just the landing app
docker compose up -d atlas-landing --no-deps

# Rebuild and restart landing app
docker compose up -d --build atlas-landing
```

#### Second Example (hermes)
```bash
cd ~/workspace/hermes

# Start all services
docker compose up -d

# Start just landing
docker compose up -d hermes-landing --no-deps
```

---

## Reference: Project Configuration

See `~/workspace/sega/config/instance1-frontend-builds.json` for the authoritative list of:
- Which projects are on which instance
- Which apps each project has (landing_app, product_app, ide, etc.)
- Which apps should be built (`"build": true` or `"build": false`)

### Key Fields
```json
{
  "name": "atlas",
  "apps": [
    {
      "name": "landing_app",
      "build": true,
      "notes": "Public marketing pages"
    },
    {
      "name": "product_app", 
      "build": true,
      "notes": "Authenticated dashboard"
    }
  ]
}
```

---

## Common Mistakes to Avoid

### ❌ WRONG: Using build-landing-apps.sh for development apps
```bash
# DO NOT DO THIS - atlas is a full development app
./scripts/build-landing-apps.sh atlas
```

**Why wrong**: This will create a standalone `atlas-landing` container that's disconnected from the backend/database/workers. The landing page won't function properly without the full stack.

### ✅ CORRECT: Use project's docker-compose.yml
```bash
# DO THIS - starts all of the project's services together
cd ~/workspace/atlas && docker compose up -d
```

---

## Verification Commands

### Check Running Containers
```bash
# All landing containers
docker ps --format 'table {{.Names}}\t{{.Ports}}' | grep landing

# Specific project
docker ps --filter 'name=atlas'
```

### Expected Results

**Demo Apps** (from build-landing-apps.sh):
- `atlas-landing` (port 3006)
- `hermes-landing` (port 3008)
- `orion-landing` (port 3000)
- etc.

**Development Apps** (from individual compose files):
- `atlas-landing` (port 3009) - PLUS atlas-api, atlas-worker, etc.
- `hermes-landing` (port 3004) - PLUS hermes-product, hermes-api, etc.

---

## Quick Reference

| Project | Type | Build Method | Container Names |
|---------|------|--------------|-----------------|
| atlas | Development | `cd ~/workspace/atlas && docker compose up -d` | atlas-landing, atlas-api, atlas-worker, etc. |
| hermes | Development | `cd ~/workspace/hermes && docker compose up -d` | hermes-landing, hermes-product, hermes-api, etc. |
| orion | Demo | `~/workspace/sega/scripts/build-landing-apps.sh orion` | orion-landing |

---

## Troubleshooting

### Container Fails with "address already in use"
See **[DOCKER_SYSTEM_SERVICE_CONFLICTS.md](../docs/operations/DOCKER_SYSTEM_SERVICE_CONFLICTS.md)** for resolving port conflicts between Docker and system services.

### Common Issues
- PostgreSQL system service using port needed by Docker → Disable system service
- Standalone Next.js server using product app port → Kill process
- Workers failing to connect → Check database container is running and healthy

---

## See Also
- **[DOCKER_SYSTEM_SERVICE_CONFLICTS.md](../docs/operations/DOCKER_SYSTEM_SERVICE_CONFLICTS.md)** - ⭐ Port conflicts & auto-start issues
- **[instance1-frontend-builds.json](../config/instance1-frontend-builds.json)** - Authoritative project configuration
- **[UNIFIED_SERVER_DEPLOYMENT.md](../docs/operations/UNIFIED_SERVER_DEPLOYMENT.md)** - Overall deployment architecture
- **[docker-compose.landing-apps.yml](../config/docker-compose.landing-apps.yml)** - Demo apps compose file
