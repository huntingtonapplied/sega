# Docker vs System Service Conflicts

**Last Updated**: 2026-02-21  
**Purpose**: Document and prevent port conflicts between Docker containers and system services

---

## Problem Overview

EC2 instances run both **Docker containers** and **system services** (PostgreSQL, Next.js servers, etc.). When both are configured to auto-start on boot, they can conflict on the same ports, causing containers to fail.

---

## Common Conflicts on Instance 1

### PostgreSQL Port Conflicts

#### Issue
System PostgreSQL clusters auto-start and occupy ports that Docker containers need.

#### Example - Service-a (Port 5009)
- **Docker**: `service-a-db` container needs port 5009
- **System**: PostgreSQL cluster `main` was auto-starting on port 5009
- **Result**: Docker container fails with "address already in use"

#### Resolution
```bash
# Check which PostgreSQL clusters are running
sudo pg_lsclusters

# Output shows:
# Ver Cluster         Port Status
# 16  service-a_5010  5010 online  <- System DB for service-a (port 5010)
# 16  service-b_5005 5005 online  <- System DB for service-b (port 5005)
# 16  main            5009 online  <- CONFLICT! This should be disabled

# Stop and disable the conflicting cluster
sudo systemctl stop postgresql@16-main
sudo systemctl disable postgresql@16-main

# Verify it's stopped
sudo pg_lsclusters
```

### Next.js Server Port Conflicts

#### Issue
Standalone Next.js servers running outside Docker occupy product app ports.

#### Example - Service-a Product (Port 4009)
- **Docker**: `service-a-product` container needs port 4009
- **System**: Standalone `next-server` process (PID 577) on port 4009
- **Result**: Docker container fails with "address already in use"

#### Resolution
```bash
# Find what's using the port
sudo netstat -tlnp | grep 4009
# Output: tcp ... LISTEN 577/next-server

# Check the process
ps -p 577 -f

# Kill the standalone server
sudo kill 577

# Start the Docker container
cd ~/projects/service-a
docker compose up -d service-a-product
```

---

## Prevention Strategy

### For Each Project

**Decision Point**: Does this project use Docker or system services?

#### Option A: Docker-Only (Recommended)
**Projects**: service-a, service-c, service-d, service-e, service-f

**Configuration**:
- ✅ Use `docker-compose.yml` for all services
- ❌ No system PostgreSQL cluster for this project
- ❌ No standalone Next.js servers

**Benefits**:
- All services managed together (`docker compose up -d`)
- No port conflicts
- Easy to start/stop entire stack

#### Option B: System Services
**Projects**: service-b (uses system PostgreSQL on port 5005)

**Configuration**:
- ✅ System PostgreSQL cluster with unique port
- ✅ System service management (`systemctl`)
- ❌ No Docker containers for these services

**Note**: Some projects intentionally use system services. Ensure ports don't conflict with Docker.

---

## Port Allocation Standards

See: [PORT_ALLOCATION_STANDARDS.md](../../docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md)

### Service-a Ports
```
3009  - Landing app (Docker)
4009  - Product app (Docker)
4109  - IDE (Docker)
5009  - Database (Docker TimescaleDB)
6009  - Redis (Docker)
8009  - API (Docker)
```

**System PostgreSQL for service-a**: Port **5010** (not 5009!)

### Service-b Ports
```
3005  - Frontend (system service)
5005  - Database (system PostgreSQL cluster)
6005  - Redis (Docker)
8005  - Backend (Docker)
```

---

## Diagnostic Commands

### Check All PostgreSQL Clusters
```bash
sudo pg_lsclusters
```

### Check What's Using a Specific Port
```bash
# Using lsof
sudo lsof -i :5009

# Using netstat
sudo netstat -tlnp | grep 5009
```

### Check All Docker Containers
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

### Check System Services
```bash
# All PostgreSQL services
sudo systemctl list-units --type=service --state=running | grep postgres

# Specific service
sudo systemctl status postgresql@16-main
```

---

## Standard Operating Procedure

### On Instance Boot

1. **System services start first** (systemd)
   - PostgreSQL clusters (if enabled)
   - Other system services

2. **Docker starts second**
   - Docker daemon starts
   - Containers with `restart: unless-stopped` start
   - **If ports conflict**: Containers fail to start

### When Adding New Projects

**Checklist**:
1. ✅ Check [PORT_ALLOCATION_STANDARDS.md](../../docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md) for assigned ports
2. ✅ Verify no system service is using those ports (`sudo lsof -i :PORT`)
3. ✅ If using system PostgreSQL, use a **different port** than Docker (e.g., 5010 vs 5009)
4. ✅ Document the decision in project's deployment docs

---

## Instance-Specific Configurations

### Instance 1 (prod-instance-01) - 203.0.113.11

**System PostgreSQL Clusters** (should remain enabled):
```bash
# Port 5005 - Service-b (system service)
postgresql@16-service-b_5005.service

# Port 5010 - Service-a (NOT used by Docker, keep for compatibility)
postgresql@16-service-a_5010.service
```

**System PostgreSQL Clusters** (should be disabled):
```bash
# Port 5009 - Conflicts with Docker service-a-db
postgresql@16-main.service  # DISABLE THIS
```

**Disable Conflicting Services**:
```bash
sudo systemctl stop postgresql@16-main
sudo systemctl disable postgresql@16-main
```

---

## Troubleshooting

### Symptom: Docker container fails with "address already in use"

**Steps**:
1. Identify the port from the error message
2. Check what's using it: `sudo lsof -i :PORT`
3. Determine if it's system service or old process
4. If system service: Disable it (see above)
5. If old process: Kill it (`sudo kill PID`)
6. Restart Docker container

### Symptom: Workers/services can't connect to database

**Check**:
1. Is the database container running? `docker ps | grep db`
2. Is it healthy? Check STATUS column
3. Are workers looking for correct hostname? (Should be service name like `postgres`, not `localhost`)
4. Check Docker network: `docker network ls` and verify containers are on same network

---

## Related Documentation

- **[PORT_ALLOCATION_STANDARDS.md](../../docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md)** - Port assignments for all projects
- **[BUILD_SCRIPTS_USAGE.md](../../scripts/BUILD_SCRIPTS_USAGE.md)** - Demo vs Development apps
- **[instance1-frontend-builds.json](../../config/instance1-frontend-builds.json)** - Frontend configuration
- **[UNIFIED_SERVER_DEPLOYMENT.md](./UNIFIED_SERVER_DEPLOYMENT.md)** - Overall deployment architecture

---

## Quick Reference

| Project | Database | Port | Type |
|---------|----------|------|------|
| service-a | Docker TimescaleDB | 5009 | Docker |
| service-b | System PostgreSQL | 5005 | System |
| service-c | Docker TimescaleDB | 5004 | Docker |
| service-d | Docker PostgreSQL | 5016 | Docker |
| service-e | Docker PostgreSQL | 5017 | Docker |
| service-f | Docker PostgreSQL | 5020 | Docker |

**Rule**: If project uses Docker for database, do NOT create a system PostgreSQL cluster for it.
