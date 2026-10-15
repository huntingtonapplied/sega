# SEGA Deployment Infrastructure

**Owner**: SEGA (Infrastructure Orchestrator)  
**Version**: 1.0.0  
**Last Updated**: 2026-02-13

## Directory Structure

```
engine/sega/deployment/
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
   - Outputs: `<workspace>/environments/package.json`

2. **`build-frontends-with-symlinks.py`**
   - Builds frontends sequentially
   - Uses shared node_modules (symlinks)
   - Configuration: `config/instance1-frontend-builds.json`

### Documentation

- **Methodology**: `frontend/FRONTEND_DEPLOYMENT_METHODOLOGY.md`
- **Configuration**: `config/instance1-frontend-builds.json`
- SEGA owns frontend deployment docs end to end.

### Quick Start

```bash
# 1. Merge dependencies
cd engine/sega/deployment/frontend
python3 merge-all-frontend-dependencies.py

# 2. Install shared dependencies
cd <workspace>/environments
npm install --legacy-peer-deps

# 3. Build all frontends
cd engine/sega/deployment/frontend
python3 build-frontends-with-symlinks.py

# 4. Check results
cat /tmp/instance1-builds.log
```

## Configuration Files

### Instance Configurations

- `config/instance1-frontend-builds.json` - Instance 1 frontend apps
- `config/instance2-frontend-builds.json` - TBD
- `config/instance3-frontend-builds.json` - TBD

### SEGA Master Config

- `config/sega.toml` - Central ecosystem configuration (start from `config/sega.toml.example`)

## Related Systems

### SEGA System Tools

- **SYSMON**: `engine/sega/system/sysmon/` - System monitoring
- **SYSNC**: `engine/sega/system/sysnc/` - Git synchronization
- **PRESERVE**: `engine/sega/system/preserve/` - Backup system
- **BRANDING**: `engine/sega/system/branding/` - Asset distribution

### Integration Points

- **Deployment docs**: SEGA owns them end to end (this directory).
- **Nginx**: Reverse proxy configs (`/sega/nginx/sites-available/`)
- **Port Standards**: `/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md`

## Version History

- **1.0.0** (2026-02-13): Initial frontend deployment infrastructure
  - Shared node_modules approach
  - Sequential build system  
  - Instance 1 configuration
