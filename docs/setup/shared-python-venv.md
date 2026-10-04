# SEGA Installation Guide: Shared Python Virtual Environment

> **2026-06-28 update — venv split + central registry.** The single `shared_venv` described below has been split into three purpose-specific venvs registered in `~/fleet/environments/projects.json`:
>
> | Venv | Marker on consumer | Consumers | Aggregated `requirements.txt` |
> |---|---|---|---|
> | `backend_venv` | `<subapp>/.venv`      | 24 | `~/fleet/environments/backend_venv/requirements.txt` |
> | `engine_venv`  | `<subapp>/.venv`      |  9 | `~/fleet/environments/engine_venv/requirements.txt` |
> | `test_venv`    | `<subapp>/.venv-test` | 25 | `~/fleet/environments/test_venv/requirements.txt` |
>
> The `requirements.txt` files are generated from each consumer's `requirements*.txt` / `pyproject.toml` by `scripts/aggregate_manifest.py --emit`. See `~/fleet/environments/STATUS.md` for the live envs table and `~/fleet/environments/MANIFEST.md` for the version-conflict report.
>
> Wire projects to the venvs with `~/fleet/environments/scripts/link_projects.sh --all` (or pass project names).

## Overview

SEGA leverages a **shared Python virtual environment (venv)** infrastructure for all portfolio backend projects to optimize disk space, installation time, and ensure version consistency.

**Key Benefits**:
- **Disk Space Reduction**: Single venv vs. individual per-project environments
- **Faster Installation**: Install dependencies once, use everywhere
- **Version Consistency**: All projects use same package versions
- **Simplified Maintenance**: Update once, apply everywhere
- **Development Simplicity**: No per-project venv activation needed

---

## Prerequisites

Before setting up shared Python venv, ensure:

- [x] Python 3.11+ installed
- [x] pip installed and updated
- [x] ~2GB free disk space
- [x] the portfolio installed at `~/fleet`

**Verify Prerequisites**:
```bash
python3 --version  # Should show 3.11.x or higher
pip3 --version     # Should be installed
df -h ~/fleet  # Should show >2GB available
```

---

## Installation

### Quick Start

```bash
# Navigate to environments directory
cd ~/fleet/environments

# Create shared virtual environment
python3 -m venv shared_venv

# Activate shared venv
source shared_venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install common dependencies
pip install \
    fastapi \
    uvicorn[standard] \
    sqlalchemy \
    alembic \
    pydantic \
    pydantic-settings \
    psycopg2-binary \
    redis \
    python-jose[cryptography] \
    passlib[bcrypt] \
    python-multipart \
    requests \
    httpx \
    pytest \
    pytest-asyncio \
    pytest-cov
```

**Expected Output**:
```
Successfully installed fastapi-0.104.1 uvicorn-0.24.0 ...
```

---

## AArchitecture

### Directory Structure

```
~/fleet/environments/
├── shared_venv/                   # ✅ Shared Python virtual environment
│   ├── bin/                   # Executables (python, pip, etc.)
│   ├── lib/                   # Python packages
│   └── pyvenv.cfg             # Virtual environment config
├── shared_node_modules/          # Shared Node.js dependencies
├── scripts/                    # Installation automation
└── README.md
```

### How It Works

1. **Single Installation**: Dependencies installed once in `~/fleet/environments/shared_venv`
2. **Project Activation**: Projects activate shared venv instead of local venv
3. **Docker Integration**: Containers mount shared venv or install from shared requirements
4. **SEGA Integration**: SEGA automatically uses shared venv for Python projects

---

## Usage

### Activating Shared Venv

**In Terminal**:
```bash
# Activate shared venv
source ~/fleet/environments/shared_venv/bin/activate

# Your prompt will change to show (shared_venv)
(shared_venv) ubuntu@host:~$

# Verify you're using shared Python
which python  # Should show ~/fleet/environments/shared_venv/bin/python
```

**Deactivating**:
```bash
deactivate
```

### Running Python Projects

**Backend Services** (e.g., an API service):
```bash
# Activate shared venv
source ~/fleet/environments/shared_venv/bin/activate

# Navigate to project
cd ~/fleet/api-service/backend

# Install any project-specific dependencies
pip install -r requirements.txt

# Run the service
export DATABASE_URL="postgresql://api-service:prophet_pass@localhost:5008/prophet_db"
export REDIS_URL="redis://:prophet_redis@localhost:6008/0"
export PYTHONPATH=~/fleet/api-service/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8008 --reload
```

**Scripts and Tools**:
```bash
# Any Python script can use shared venv
source ~/fleet/environments/shared_venv/bin/activate
python ~/fleet/docs/secretary/scripts/some_tool.py
```

### Adding Project Dependencies

When a project needs additional packages:

```bash
# Activate shared venv
source ~/fleet/environments/shared_venv/bin/activate

# Install project-specific requirements
cd ~/fleet/<project>/backend
pip install -r requirements.txt

# Dependencies are now available to ALL projects
```

---

## Integration with SEGA

### Docker Development Mode

For development with Docker and shared venv:

```yaml
# docker-compose.yml
services:
  backend:
    volumes:
      - ./backend:/app
      - ~/fleet/environments/shared_venv:/venv:ro
    environment:
      VIRTUAL_ENV: /venv
      PATH: /venv/bin:$PATH
```

### Direct Execution (Recommended for EC2)

For EC2 instances, running services directly with shared venv is recommended:

```bash
# One-time setup: Activate venv in .bashrc
echo 'source ~/fleet/environments/shared_venv/bin/activate' >> ~/.bashrc

# Now every terminal automatically has access to shared Python packages
```

---

## Project-Specific Setup

### Backend Example

```bash
# 1. Ensure shared venv is active
source ~/fleet/environments/shared_venv/bin/activate

# 2. Navigate to project
cd ~/fleet/api-service/backend

# 3. Install project dependencies
pip install -r requirements.txt

# 4. Set environment variables
export DATABASE_URL="postgresql://api-service:prophet_pass@localhost:5008/prophet_db"
export REDIS_URL="redis://:prophet_redis@localhost:6008/0"
export PYTHONPATH=~/fleet/api-service/backend

# 5. Run the service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8008 --reload
```

### Secondary Backend Example

```bash
# Activate and navigate
source ~/fleet/environments/shared_venv/bin/activate
cd ~/fleet/service-b/backend

# Install scientific computing dependencies
pip install -r requirements.txt  # numpy, scipy, pandas, etc.

# Run service-b API
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

---

## Maintenance

### Updating Shared Dependencies

```bash
# Activate shared venv
source ~/fleet/environments/shared_venv/bin/activate

# Update all packages
pip list --outdated
pip install --upgrade <package-name>

# Or update everything (use with caution)
pip freeze > current_packages.txt
pip install --upgrade pip
pip list --outdated | cut -d ' ' -f1 | xargs -n1 pip install -U
```

### Reinstalling Shared Venv

If the shared venv becomes corrupted:

```bash
# Backup current packages
source ~/fleet/environments/shared_venv/bin/activate
pip freeze > /tmp/fleet_venv_backup.txt
deactivate

# Remove and recreate
rm -rf ~/fleet/environments/shared_venv
python3 -m venv ~/fleet/environments/shared_venv

# Restore packages
source ~/fleet/environments/shared_venv/bin/activate
pip install --upgrade pip
pip install -r /tmp/fleet_venv_backup.txt
```

---

## Verification

### Health Check

```bash
# 1. Check venv exists
ls -la ~/fleet/environments/shared_venv/bin/python

# 2. Activate and verify
source ~/fleet/environments/shared_venv/bin/activate

# 3. Check Python version
python --version  # Should be 3.11+

# 4. List installed packages
pip list | head -20

# 5. Verify critical packages
python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
python -c "import sqlalchemy; print('SQLAlchemy:', sqlalchemy.__version__)"
python -c "import pydantic; print('Pydantic:', pydantic.__version__)"
python -c "import pydantic_settings; print('Pydantic Settings: OK')"
```

**Expected Output**:
```
Python 3.12.3
FastAPI: 0.104.1
SQLAlchemy: 2.0.23
Pydantic: 2.5.0
Pydantic Settings: OK
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'X'"

**Cause**: Package not installed in shared venv

**Solution**:
```bash
source ~/fleet/environments/shared_venv/bin/activate
pip install <missing-package>
```

### Issue: "externally-managed-environment" error

**Cause**: Trying to install to system Python instead of venv

**Solution**:
```bash
# Always activate venv first
source ~/fleet/environments/shared_venv/bin/activate
# Then install
pip install <package>
```

### Issue: Virtual environment not found

**Cause**: Shared venv not created yet

**Solution**:
```bash
cd ~/fleet/environments
python3 -m venv shared_venv
source shared_venv/bin/activate
pip install --upgrade pip
```

### Issue: Permission denied when activating venv

**Cause**: Incorrect permissions on venv directory

**Solution**:
```bash
sudo chown -R ubuntu:ubuntu ~/fleet/environments/shared_venv
chmod -R u+rwX ~/fleet/environments/shared_venv
```

---

## Best Practices

### Do's ✅
- Always activate shared venv before running Python code
- Install all common dependencies in shared venv
- Use `pip freeze` to document installed packages
- Test projects after updating shared venv packages

### Don'ts ❌
- Don't create project-specific venvs (`python -m venv venv` in project dirs)
- Don't install packages to system Python (`pip install --break-system-packages`)
- Don't modify shared venv from multiple terminals simultaneously
- Don't delete shared venv without backing up package list

---

## Integration with Other Systems

### GitLab CI/CD

In `.gitlab-ci.yml`:
```yaml
before_script:
  - source ~/fleet/environments/shared_venv/bin/activate
  - pip install -r requirements.txt

test:
  script:
    - pytest tests/
```

### Systemd Services

For background services:
```ini
[Service]
ExecStart=~/fleet/environments/shared_venv/bin/python -m uvicorn app.main:app
Environment="PYTHONPATH=~/fleet/api-service/backend"
```

### Terminal Orchestration

Shared venv automatically available in all terminal workspaces when added to `.bashrc`.

---

## Related Documentation

- [Shared Node Modules Installation](./shared-node-modules.md)
- [EC2 GitLab SSH Setup](~/fleet/docs/guides/migration/EC2_GITLAB_SSH_SETUP.md)
- [Environments README](~/fleet/environments/README.md)
- [SEGA Local Development](~/fleet/sega/docs/usage/LOCAL_DEVELOPMENT.md)

---

**Last Updated**: 2025-10-06
**Status**: ✅ Active - All portfolio Python projects use shared venv
**Maintainer**: DevOps Team
