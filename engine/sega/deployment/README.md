# SEGA Deployment Infrastructure

**Owner**: SEGA (Infrastructure Orchestrator)  
**Version**: 1.0.0  
**Last Updated**: 2026-02-13

## Directory Structure

```
~/fleet/sega/engine/sega/deployment/
├── frontend/
│   ├── FRONTEND_DEPLOYMENT_METHODOLOGY.md  # Complete deployment guide
│   ├── merge-all-frontend-dependencies.py  # Dependency merger
│   └── build-frontends-with-symlinks.py    # Sequential build tool
└── README.md                                # This file
```

## Frontend Deployment

### Tools

1. **`merge-all-frontend-dependencies.py`**
   - Scans all project frontends
   - Merges package.json files
   - Outputs: `~/fleet/environments/package.json`

2. **`build-frontends-with-symlinks.py`**
   - Builds frontends sequentially
   - Uses shared node_modules (symlinks)
   - Configuration: `~/fleet/sega/config/instance1-frontend-builds.json`

### Documentation

- **Methodology**: `frontend/FRONTEND_DEPLOYMENT_METHODOLOGY.md`
- **Configuration**: `~/fleet/sega/config/instance1-frontend-builds.json`
- (The former `~/fleet/dispatcher/docs/deployment/FRONTEND_DEPLOYMENT.md` was removed in the 2026-07-01 dispatcher purge; SEGA owns frontend deployment.)

### Quick Start

```bash
# 1. Merge dependencies
cd ~/fleet/sega/engine/sega/deployment/frontend
python3 merge-all-frontend-dependencies.py

# 2. Install shared dependencies
cd ~/fleet/environments
npm install --legacy-peer-deps

# 3. Build all frontends
cd ~/fleet/sega/engine/sega/deployment/frontend
python3 build-frontends-with-symlinks.py

# 4. Check results
cat /tmp/instance1-builds.log
```

## Configuration Files

### Instance Configurations

- `~/fleet/sega/config/instance1-frontend-builds.json` - Instance 1 frontend apps
- `~/fleet/sega/config/instance2-frontend-builds.json` - TBD
- `~/fleet/sega/config/instance3-frontend-builds.json` - TBD

### SEGA Master Config

- `~/fleet/sega/config/sega.toml` - Central ecosystem configuration

## Related Systems

### SEGA System Tools

- **SYSMON**: `~/fleet/sega/engine/sega/system/sysmon/` - System monitoring
- **SYSNC**: `~/fleet/sega/engine/sega/system/sysnc/` - Git synchronization
- **PRESERVE**: `~/fleet/sega/engine/sega/system/preserve/` - Backup system
- **BRANDING**: `~/fleet/sega/engine/sega/system/branding/` - Asset distribution

### Integration Points

- **DISPATCHER**: (previously held high-level orchestration docs at `/dispatcher/docs/deployment/`; removed in 2026-07-01 purge — SEGA now owns deployment docs end-to-end)
- **Nginx**: Reverse proxy configs (`/sega/nginx/sites-available/`)
- **Port Standards**: `/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md`

## Version History

- **1.0.0** (2026-02-13): Initial frontend deployment infrastructure
  - Shared node_modules approach
  - Sequential build system  
  - Instance 1 configuration
