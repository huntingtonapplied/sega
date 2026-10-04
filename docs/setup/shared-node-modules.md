# SEGA Installation Guide: Shared Node Modules

> **2026-06-28 update — source of truth moved.** Per-env install manifests are now generated from a central registry at `~/fleet/environments/projects.json`. See `~/fleet/environments/STATUS.md` for the current envs table (landing_app, product_app, ide, desktop, expo, extension) and consumer counts. The legacy `scripts/install_shared_deps.sh` / `aggregate_deps.py` paths described below still exist; the new flow is:
>
> ```bash
> # Regenerate every env's package.json from live project deps
> python3 ~/fleet/environments/scripts/aggregate_manifest.py --emit
>
> # Wire (or rewire) project subapps to the shared envs
> ~/fleet/environments/scripts/link_projects.sh --all
> # or pick projects:  link_projects.sh service-d service-e service-f
> ```
>
> The version-conflict report lives at `~/fleet/environments/MANIFEST.md` — read it before bumping any package across consumers.

## Overview

SEGA leverages a **shared node_modules** infrastructure for all portfolio frontend projects to optimize disk space, installation time, and build performance.

> **⚠️ SEGA-Only Feature**: Shared node_modules is specific to SEGA local development mode (`sega local up`). Docker Compose deployments use **isolated dependencies** - each container runs `npm ci` independently. See the comparison below.

> **⚠️ IDE Projects Exception**: VS Code-based IDE projects (e.g., `web-app/ide`) require their own isolated `node_modules` due to unique VS Code dependencies. Use `npm install` in the IDE directory, **NOT** shared node_modules.

**Key Benefits** (SEGA Local Mode):
- **75% Disk Space Reduction**: 8.5GB shared vs. 34GB individual
- **82% Faster Installation**: 15 minutes vs. 85 minutes
- **Version Consistency**: All projects use same dependency versions
- **Simplified Maintenance**: Update once, apply everywhere

### SEGA Local vs Docker Compose

| Aspect | SEGA Local (This Guide) | Docker Compose |
|--------|-------------------------|----------------|
| **node_modules** | Shared (symlinked) | Isolated (per container) |
| **Location** | `~/fleet/environments/node_modules` | Inside each container |
| **Install** | Once, shared across projects | Per container on build |
| **Use case** | Development iteration | CI/CD, production |
| **Isolation** | Low (shared versions) | High (full isolation) |

For Docker Compose patterns, see:
- **[UIX_SPLIT_ROUTING_ARCHITECTURE.md](/docs/templates/web/react/guides/UIX_SPLIT_ROUTING_ARCHITECTURE.md)** - Single Dockerfile pattern
- **[FRONTEND_TESTING_MODES.md](/docs/standards/infrastructure/FRONTEND_TESTING_MODES.md)** - Consolidated testing modes

---

## Prerequisites

Before setting up shared node_modules, ensure:

- [x] Node.js 20.x or higher installed
- [x] npm 9.x or higher installed
- [x] ~10GB free disk space
- [x] SEGA installed at `~/fleet/sega`

**Verify Prerequisites**:
```bash
node --version  # Should show v20.x or higher
npm --version   # Should show 9.x or higher
df -h ~/fleet  # Should show >10GB available
```

---

## Installation

### Quick Start

```bash
# Navigate to environments directory
cd ~/fleet/environments

# Run installation script
./scripts/install_shared_deps.sh

# Verify installation
./scripts/verify_shared_deps.sh
```

### Usage Options

```bash
./scripts/install_shared_deps.sh --help
./scripts/install_shared_deps.sh --exclude landing_app
./scripts/install_shared_deps.sh --exclude web-app:landing_app
./scripts/install_shared_deps.sh --exclude "web-app,service-c"
```

**Expected Output**:
```
========================================
Shared Node Modules Installation
========================================

[1/5] Checking Node.js and npm...
✓ Node.js v20.11.1
✓ npm 10.2.4

[2/5] Aggregating dependencies from all projects...
# Aggregated 164 unique dependencies
# From your projects: web-app, service-a, service-b, ...
✓ Created package.json

[3/5] Installing dependencies...
Running npm install (this may take 5-15 minutes)...
✓ Installed 1367 packages (8.5GB)

[4/5] Creating symlinks in project frontends...
  ✓ service-a
  ✓ web-app
  ✓ service-b
  ...
✓ Linked 17 projects

[5/5] Installation complete!
```

---

## AArchitecture

### Directory Structure

```
~/fleet/
├── environments/
│   ├── shared_node_modules/              # SHARED NODE_MODULES (frontends)
│   │   ├── node_modules/              # 1367 packages (8.5GB)
│   │   ├── .bin/                      # npm binaries
│   │   ├── package.json               # Aggregated dependencies (164 packages)
│   │   └── package-lock.json          # Locked versions
│   ├── scripts/
│   │   ├── aggregate_deps.py          # Dependency aggregation
│   │   ├── install_shared_deps.sh     # Installation script
│   │   └── verify_shared_deps.sh      # Verification script
│   └── README.md                      # Environment documentation
│
├── service-a/frontend/
│   └── node_modules -> ~/fleet/environments/shared_node_modules/node_modules
│
├── web-app/frontend/
│   └── node_modules -> ~/fleet/environments/shared_node_modules/node_modules
│
├── web-app/ide/
│   └── node_modules/                  # ⚠️ ISOLATED (VS Code dependencies)
│
└── [15 more projects...]
```

### How It Works

1. **Aggregation**: Script reads all `frontend/package.json` files across 17 projects
2. **Version Resolution**: Merges dependencies, keeping highest version for conflicts
3. **Installation**: Single `npm install` in `~/fleet/environments/shared_node_modules`
4. **Symlinking**: Each project's `frontend/node_modules` symlinks to shared directory
5. **Build Integration**: Projects access dependencies through symlink

---

## SEGA Integration

### Automatic Detection

SEGA automatically detects and uses shared node_modules:

```bash
cd ~/fleet/<project>
sega local up --with-frontend
```

**SEGA Checks**:
1. ✓ Shared node_modules exists at `~/fleet/environments/shared_node_modules`
2. ✓ Project's `frontend/node_modules` symlink is valid
3. ✓ PATH includes shared `.bin` directory
4. ✓ All required dependencies are installed

### PATH Configuration

SEGA automatically sets PATH for frontend builds:

```bash
export PATH="~/fleet/environments/shared_node_modules/.bin:$PATH"
```

Add to your `~/.bashrc` for manual builds:
```bash
echo 'export PATH="~/fleet/environments/shared_node_modules/.bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Docker Integration

SEGA mounts shared node_modules in Docker containers:

```yaml
# docker-compose.yml (auto-generated by SEGA)
services:
  frontend:
    volumes:
      - ./frontend:/app
      - ~/fleet/environments/shared_node_modules/node_modules:/app/node_modules:ro
```

---

## Manual Testing

### Test Single Project Build

```bash
cd ~/fleet/web-app/frontend
export PATH="~/fleet/environments/shared_node_modules/.bin:$PATH"
npm run build
```

**Expected Output**:
```
▲ Next.js 14.2.10
Creating an optimized production build ...
✓ Compiled successfully
```

### Test All Projects

```bash
cd ~/fleet/environments
./scripts/verify_builds.sh
```

**Expected Output**:
```
Testing builds for 17 projects...
✓ service-a: Build successful
✓ web-app: Build successful
✓ service-b: Build successful
...
Summary: 15/17 passed, 2/17 failed
```

---

## Special Cases

### IDE Projects (VS Code-based)

**Projects with IDE interfaces** (e.g., `web-app/ide`) are based on VS Code and require isolated `node_modules`:

#### Why IDE Projects Are Different

- **VS Code Dependencies**: Unique packages like `@vscode/*`, `electron`, `playwright`
- **Build Tools**: Custom gulp tasks and TypeScript compilation
- **Size**: ~2-3GB of IDE-specific dependencies
- **Incompatibility**: Cannot share with Next.js/React frontends

#### Installation for IDE Projects

```bash
# Navigate to IDE directory
cd ~/fleet/web-app/ide

# Install IDE dependencies (takes 10-15 minutes)
npm install

# Verify installation
ls -la node_modules | head -10
# Should show actual directory, NOT a symlink

# Build IDE (transpile TypeScript to JavaScript)
npm run gulp -- transpile-client-esbuild
```

#### DO NOT Create Symlink

```bash
# ❌ WRONG - Do not symlink IDE to shared node_modules
cd ~/fleet/web-app/ide
ln -s ~/fleet/environments/node_modules node_modules  # DO NOT DO THIS

# ✅ CORRECT - Use isolated node_modules
npm install
```

#### Projects with IDE Component

| Project | IDE Location | Install Command |
|---------|--------------|-----------------|
| **web-app** | `web-app/ide/` | `cd ide && npm install` |

---

## Troubleshooting

### Issue: "Module not found" Error

**Symptom**:
```
Module not found: Can't resolve 'react-intl'
```

**Cause**: Project requires dependency not in shared node_modules

**Fix**:
```bash
# 1. Check if dependency is in project's package.json
cat ~/fleet/<project>/frontend/package.json | grep react-intl

# 2. If yes, reinstall shared dependencies
cd ~/fleet/environments
./scripts/install_shared_deps.sh --force

# 3. If no, add to project's package.json
cd ~/fleet/<project>/frontend
# Edit package.json to add dependency
# Then reinstall
cd ~/fleet/environments
./scripts/install_shared_deps.sh --force
```

### Issue: Broken Symlink

**Symptom**:
```bash
ls -la ~/fleet/service-a/frontend/node_modules
# Shows: node_modules -> ~/fleet/environments/shared_node_modules/node_modules (broken)
```

**Fix**:
```bash
cd ~/fleet/service-a/frontend
rm node_modules
ln -sf ~/fleet/environments/shared_node_modules/node_modules node_modules
```

### Issue: Version Conflicts

**Symptom**: Build works in one project but fails in another

**Cause**: Projects require incompatible versions

**Fix 1 - Update Project** (Recommended):
```bash
# Update project to use version in shared node_modules
cd ~/fleet/<project>/frontend
# Edit package.json to match shared version
cd ~/fleet/environments
./scripts/install_shared_deps.sh --force
```

**Fix 2 - Project-Specific Override** (NOT RECOMMENDED):
```bash
# Give project its own node_modules
cd ~/fleet/<project>/frontend
rm node_modules  # Remove symlink
npm install      # Install project-specific deps
```

### Issue: npm Command Not Found

**Symptom**:
```bash
npm run build
# Error: npm: command not found
```

**Cause**: PATH not set correctly

**Fix**:
```bash
export PATH="~/fleet/environments/shared_node_modules/.bin:$PATH"
npm run build
```

---

## Maintenance

### Update All Dependencies

```bash
cd ~/fleet/environments/shared_node_modules
npm update
npm audit fix
```

### Add New Project

```bash
# 1. Ensure project has frontend/package.json
ls -la ~/fleet/<new_project>/frontend/package.json

# 2. Reinstall shared dependencies (includes new project)
cd ~/fleet/environments
./scripts/install_shared_deps.sh --force

# 3. Verify symlink created
ls -la ~/fleet/<new_project>/frontend/node_modules
```

### Clean Reinstall

```bash
cd ~/fleet/environments
rm -rf shared_node_modules
./scripts/install_shared_deps.sh
```

---

## Performance Metrics

### Disk Space Comparison

| Configuration | Space Used | Projects | Average per Project |
|--------------|------------|----------|---------------------|
| Individual node_modules | ~34GB | 17 | 2GB |
| Shared node_modules | 8.5GB | 17 | 0.5GB |
| **Savings** | **25.5GB (75%)** | - | **1.5GB per project** |

### Installation Time Comparison

| Configuration | Total Time | Projects | Average per Project |
|--------------|------------|----------|---------------------|
| Individual installs | 85 minutes | 17 | 5 minutes |
| Shared install | 15 minutes | 17 | <1 minute |
| **Savings** | **70 minutes (82%)** | - | **4 minutes per project** |

### Build Performance

| Metric | Individual | Shared | Improvement |
|--------|-----------|--------|-------------|
| First build | 45s | 45s | 0% (same) |
| Incremental build | 8s | 7s | 12% faster |
| Parallel builds | Disk thrashing | Smooth | Significant |

---

## Security Considerations

### Vulnerability Scanning

```bash
cd ~/fleet/environments/shared_node_modules
npm audit

# Current status (2025-10-06):
# 26 vulnerabilities (13 moderate, 8 high, 5 critical)
```

**Recommended Actions**:
```bash
# Fix vulnerabilities (safe)
npm audit fix

# Force fix (may break compatibility - test thoroughly)
npm audit fix --force
```

### Package Integrity

All packages installed with integrity verification:
```bash
npm install --integrity-check
```

---

## Migration from Per-Project node_modules

If your projects currently have individual `node_modules` directories:

### Backup Strategy

```bash
# For each project, backup existing node_modules
for project in web-app service-a service-b service-c api-service; do
    frontend_dir="~/fleet/$project/frontend"
    if [ -d "$frontend_dir/node_modules" ] && [ ! -L "$frontend_dir/node_modules" ]; then
        echo "Backing up $project..."
        mv "$frontend_dir/node_modules" "$frontend_dir/node_modules.backup"
    fi
done
```

### Install Shared node_modules

```bash
cd ~/fleet/environments
./scripts/install_shared_deps.sh
```

### Verify and Clean Up

```bash
# Test builds
cd ~/fleet/environments
./scripts/verify_builds.sh

# If all pass, remove backups
for project in web-app service-a service-b service-c api-service; do
    frontend_dir="~/fleet/$project/frontend"
    if [ -d "$frontend_dir/node_modules.backup" ]; then
        echo "Removing backup from $project..."
        rm -rf "$frontend_dir/node_modules.backup"
    fi
done
```

---

## Advanced Configuration

### Custom Shared Location

To use a different location for shared node_modules:

```bash
# 1. Edit install_shared_deps.sh
vim ~/fleet/environments/scripts/install_shared_deps.sh
# Change: SHARED_DIR="/your/custom/path"

# 2. Run installation
./scripts/install_shared_deps.sh

# 3. Update SEGA configuration
vim ~/fleet/sega/config/shared_paths.yaml
# Add: node_modules_path: "/your/custom/path"
```

### Exclude Projects or Apps

Use `--exclude` to skip projects or app folders (comma-separated values supported):

```bash
# Exclude all landing apps across projects
cd ~/fleet/environments
./scripts/install_shared_deps.sh --exclude landing_app

# Exclude a single app in a project
./scripts/install_shared_deps.sh --exclude web-app:landing_app

# Exclude entire projects
./scripts/install_shared_deps.sh --exclude "web-app,service-c"
```

If you want full manual control, install without symlinks and link only what you need:

```bash
cd ~/fleet/environments
./scripts/install_shared_deps.sh --skip-symlinks

for project in web-app service-a service-b; do
    cd ~/fleet/$project/frontend
    ln -sf ~/fleet/environments/shared_node_modules/node_modules node_modules
done
```


---

## References

- **Environment README**: `~/fleet/environments/README.md`
- **Aggregation Script**: `~/fleet/environments/scripts/aggregate_deps.py`
- **SEGA Main Installation**: `~/fleet/sega/docs/setup/installation.md`
- **Render Verification**: `~/fleet/docs/reports/RENDER_VERIFICATION_PROGRESS_20251006.md`
- **Build Failure Analysis**: `~/fleet/docs/reports/BUILD_FAILURE_ANALYSIS_20251006.md`

---

## Support

**Issues**: Report to `your project issue tracker`
**Updates**: Document in `~/fleet/environments/CHANGELOG.md`
**Maintainer**: Infrastructure Team / SEGA Orchestration
