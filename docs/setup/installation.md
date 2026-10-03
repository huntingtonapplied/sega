# SEGA Installation Guide

**Version**: 1.0
**Last Updated**: October 6, 2025
**Maintainer**: Infrastructure Team

---

## Overview

SEGA is the fleet CLI — one command grammar for a whole portfolio of services, the central orchestration platform for your projects, providing unified CI/CD, deployment management, and infrastructure coordination across your projects.

**Key Features**:
- Multi-domain deployment (software, embedded, FPGA, bare-metal)
- Shared infrastructure management (PostgreSQL, Redis, TimescaleDB)
- Advanced testing frameworks (browser, mobile, desktop, hardware)
- GitLab CI/CD integration with encrypted secrets management

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Shared Node Modules Setup](#shared-node-modules-setup)
4. [SEGA Core Installation](#sega-core-installation)
5. [Project Integration](#project-integration)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 22.04+), macOS 12+
- **Python**: 3.10 or higher
- **Node.js**: 20.x or higher
- **npm**: 9.x or higher
- **Docker**: 20.10+ with Docker Compose
- **Disk Space**: 20GB minimum (50GB recommended)
- **Memory**: 8GB minimum (16GB recommended)

### Required Tools

```bash
# Verify installations
python3 --version  # Should be 3.10+
node --version     # Should be v20.x+
npm --version      # Should be 9.x+
docker --version   # Should be 20.10+
docker compose version  # Should be v2.0+
```

### Install Missing Tools

**Python 3.10+**:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# macOS
brew install python@3.11
```

**Node.js 20+**:
```bash
# Using nvm (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 20
nvm use 20

# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# macOS
brew install node@20
```

**Docker**:
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
newgrp docker

# macOS
brew install --cask docker
```

---

## Quick Start

For experienced users who want to get SEGA running immediately:

```bash
# 1. Clone the portfolio repository (if not already cloned)
git clone <repo-url> ~/fleet
cd ~/fleet

# 2. Install shared node_modules (required for frontends)
cd ~/fleet/environments
./scripts/install_shared_deps.sh

# 3. Install SEGA
cd ~/fleet/sega
pip3 install -e .

# 4. Verify installation
sega --version
sega detect --all

# 5. Test deployment
cd ~/fleet/web-app
sega local up --with-frontend
```

---

## Shared Node Modules Setup

**IMPORTANT**: All portfolio frontend projects use a shared node_modules infrastructure. This must be installed **before** building any frontends.

### Why Shared Node Modules?

- **Disk Space**: Saves ~25GB (75% reduction)
- **Installation Time**: 15 minutes vs. 85 minutes (82% faster)
- **Version Consistency**: All projects use same dependencies
- **Simplified Maintenance**: Update once, apply everywhere

### Installation

```bash
cd ~/fleet/environments
./scripts/install_shared_deps.sh
```

**What This Does**:
1. Aggregates dependencies from 17 frontend projects (164 unique packages)
2. Installs all dependencies to `~/fleet/environments/shared_node_modules`
3. Creates symlinks in each project's `frontend/node_modules`

**Verification**:
```bash
# Check installation
ls -la ~/fleet/environments/shared_node_modules/node_modules | wc -l
# Should show ~1367 packages

# Check symlinks
ls -la ~/fleet/web-app/frontend/node_modules
# Should show: node_modules -> ~/fleet/environments/shared_node_modules/node_modules
```

**For Complete Documentation**: See [shared-node-modules.md](./shared-node-modules.md)

---

## SEGA Core Installation

### Step 1: Create Python Virtual Environment

```bash
cd ~/fleet/sega
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install SEGA

```bash
# Development installation (recommended)
pip install -e .

# Or production installation
pip install .
```

**Expected Output**:
```
Successfully installed sega-1.0.0
Installing 26 CLI commands...
✓ sega detect
✓ sega local
✓ sega test
✓ sega deploy
... (22 more commands)
```

### Step 3: Verify Installation

```bash
sega --version
# Output: sega version 1.0.0

sega --help
# Output: Shows all 26 available commands
```

### Step 4: Configure Environment Variables

```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="~/fleet/environments/shared_node_modules/.bin:$PATH"
export SEGA_HOME="~/fleet/sega"

# Reload shell
source ~/.bashrc
```

---

## Project Integration

### Automatic Detection

SEGA automatically detects project types and configurations:

```bash
cd ~/fleet/<project>
sega detect

# Output:
# Project: web-app
# Type: web-fullstack
# Backend: FastAPI (Python)
# Frontend: Next.js (TypeScript)
# Database: PostgreSQL
# Ports: Backend=8003, Frontend=3007, Database=5007
```

### Test All Projects

```bash
cd ~/fleet/sega
sega detect --all

# Output: Shows detection results for all portfolio projects
```

### Deploy Single Project

```bash
cd ~/fleet/<project>
sega local up

# With frontend:
sega local up --with-frontend

# Specific services:
sega local up --services backend,database
```

---

## Verification

### Test Backend Deployment

```bash
cd ~/fleet/web-app
sega local up --services backend

# Verify
curl http://localhost:8003/health
# Expected: {"status": "healthy", "database": "connected"}
```

### Test Frontend Build

```bash
cd ~/fleet/web-app/frontend
export PATH="~/fleet/environments/shared_node_modules/.bin:$PATH"
npm run build

# Expected: ✓ Compiled successfully
```

### Test Full Stack

```bash
cd ~/fleet/web-app
sega local up --with-frontend

# Verify backend
curl http://localhost:8003/health

# Verify frontend
curl http://localhost:30030
# Should return HTML
```

### Run Tests

```bash
cd ~/fleet/<project>
sega test

# Browser tests:
sega test --browser

# Mobile tests:
sega test --mobile
```

---

## Troubleshooting

### Issue: "sega: command not found"

**Cause**: SEGA not in PATH or virtual environment not activated

**Fix**:
```bash
# Activate venv
cd ~/fleet/sega
source .venv/bin/activate

# Or reinstall
pip install -e .
```

### Issue: "Module not found" in Frontend Build

**Cause**: Shared node_modules not installed or symlink broken

**Fix**:
```bash
# Reinstall shared node_modules
cd ~/fleet/environments
./scripts/install_shared_deps.sh --force

# Verify symlink
ls -la ~/fleet/<project>/frontend/node_modules
```

### Issue: Docker Container Won't Start

**Cause**: Port conflict or missing environment variables

**Fix**:
```bash
# Check ports
docker ps | grep <project>
lsof -i :<port>

# Check environment
cd ~/fleet/<project>
cat .env
# Ensure all required variables are set

# View logs
docker logs <container-name>
```

### Issue: Database Connection Failed

**Cause**: Database service not running or incorrect connection string

**Fix**:
```bash
# Check database status
docker ps | grep postgres

# Start database
cd ~/fleet/<project>
docker compose up -d postgres

# Verify connection
docker exec -it <project>_postgres psql -U <user> -d <database> -c "SELECT 1;"
```

### Issue: Build Timeout

**Cause**: Network issues or large dependency download

**Fix**:
```bash
# Increase timeout
docker compose build --build-arg TIMEOUT=600 backend

# Use shared npm cache
export npm_config_cache=~/fleet/environments/.npm-cache
npm install
```

---

## Advanced Configuration

### Custom Port Allocation

Edit project's `.sega/laboratory_config.yaml`:
```yaml
ports:
  backend: 8099  # Custom backend port
  frontend: 3099  # Custom frontend port
  database: 5099  # Custom database port
```

### Environment-Specific Configuration

```bash
# Development
export SEGA_ENV=development
sega local up

# Staging
export SEGA_ENV=staging
sega local up

# Production
export SEGA_ENV=production
sega deploy
```

### Custom Deployment Options

```bash
# Deploy with specific Docker Compose file
sega local up --compose-file docker-compose.custom.yml

# Deploy with resource limits
sega local up --memory 4g --cpus 2

# Deploy with custom network
sega local up --network custom-network
```

---

## Installation Architecture

### Three-Phase Installation Flow

```
Phase 1: Bootstrap
fleet_install → Clone the portfolio repo + Install SEGA + Basic system deps

Phase 2: System Configuration
sega install --target <system-type> → Configure system for specific role

Phase 3: Service Deployment
sega deploy --production → Deploy and manage services
```

### System Types

SEGA supports different installation profiles:

**Development Systems:**
- `mac-dev` - macOS development (Python, Node.js, Docker Desktop)
- `development-jellyfish` - Linux development (Python, Node.js, Docker CE)
- `hardware-dev-mac-jellyfish` - Hardware development with FPGA/embedded tools

**Production Systems:**
- `server-jellyfish` - Full production server (Docker, PostgreSQL, Redis, Nginx, VPN server)
- `engine-jellyfish` - Python engine runtime (minimal)
- `platform-jellyfish` - Platform services (Docker, databases, Nginx)
- `omni-jellyfish` - All projects production (full portfolio stack)

**Usage:**
```bash
sega install --list-targets        # Show available system types
sega install --detect              # Auto-detect recommended type
sega install --target mac-dev      # Install specific type
```

---

## Next Steps

After successful installation:

1. **Read Project Documentation**:
   - [SEGA Architecture](~/fleet/sega/docs/architecture/architecture_summary.yaml)
   - [CLI Command Reference](~/fleet/sega/docs/reference/CLI.md)
   - [Deployment Options](~/fleet/sega/docs/deployment/SEGA_DEPLOYMENT_OPTIONALITY_MATRIX.md)

2. **Explore Features**:
   ```bash
   sega secrets list          # View encrypted secrets
   sega test --browser        # Run browser tests
   sega deploy --dry-run      # Preview deployment
   ```

3. **Integrate with GitLab CI/CD**:
   - [GitLab Integration Guide](~/fleet/sega/docs/deployment/GITLAB_CI_CD.md)

4. **Set Up Monitoring**:
   - [Telemetry Integration](~/fleet/metrics-service/docs/SEGA_INTEGRATION.md)

---

## Support & Resources

- **Documentation**: `~/fleet/sega/docs/`
- **Issues**: Report to `your project issue tracker`
- **Updates**: `~/fleet/sega/CHANGELOG.md`
- **Examples**: `~/fleet/sega/examples/`

**Maintainer**: Infrastructure Team
**Repository**: `~/fleet/sega`
**Version**: 1.0.0
