# SYSMON - FLEET System Monitor

**Purpose**: Unified CLI tool for disk usage analysis, system monitoring, and cleanup operations across local and EC2 instances.

**Location**: `/sega/engine/sega/system/sysmon/`

**Full Procedure**: See [Disk Usage Management Procedure](/docs/guides/procedures/DISK_USAGE_MANAGEMENT.md)

---

## Quick Start

```bash
# Add to PATH (optional)
export PATH="$PATH:$HOME/fleet/sega/engine/sega/system/sysmon"

# Or run directly
~/fleet/sega/engine/sega/system/sysmon/sysmon <command>

# Or use via SEGA CLI
sega sysmon <command>
```

## Commands Overview

| Command | Description |
|---------|-------------|
| `sysmon status` | Quick status check (local or remote) |
| `sysmon analyze` | Deep disk and system analysis |
| `sysmon dashboard` | Multi-instance 4-table view |
| `sysmon projects` | Project-based metrics dashboard |
| `sysmon cleanup docker` | Docker cleanup operations |
| `sysmon cleanup builds` | Build artifact cleanup (+ Rust targets) |
| `sysmon cleanup caches` | System cache cleanup (npm, cargo, claude) |
| `sysmon cleanup preserves` | Backup/preserve cleanup with retention |
| `sysmon report` | Generate markdown/JSON reports |
| `sysmon help` | Show help |

---

## Command Reference

### sysmon status

Quick status check for local or remote instances.

```bash
sysmon status                  # Local status
sysmon status --instance 1     # Instance 1 only
sysmon status --instance 2     # Instance 2 only
sysmon status --all            # All instances
```

**Output includes**:
- Disk usage with color-coded percentage
- Memory usage
- Docker container count
- Claude/tmux sessions
- Load average

---

### sysmon analyze

Comprehensive disk and system analysis with cleanup recommendations.

```bash
sysmon analyze                      # Full local analysis
sysmon analyze --with-cpu           # Include CPU/memory metrics
sysmon analyze --output report.md   # Save to file
sysmon analyze --instance 1         # Analyze Instance 1
```

**Options**:
- `--with-cpu` - Include CPU, memory, processes, Docker container stats, database storage
- `--output <file>` - Save report to file (default: /tmp/sysmon_analysis_*.md)
- `--instance <n>` - Analyze specific remote instance

**Analysis includes**:
- System disk overview with warnings
- Top-level directory breakdown
- Docker usage (images, containers, cache, volumes)
- FLEET directory analysis (projects, node_modules, build artifacts)
- Large file detection (>100MB)
- Database storage by project (with --with-cpu)
- Automatic cleanup recommendations

---

### sysmon dashboard

Multi-instance dashboard with 4-table view (Storage + CPU/Usage for each instance).

```bash
sysmon dashboard          # Full dashboard (~30s)
sysmon dashboard --quick  # Skip DB volume sizing (~10s)
```

**Options**:
- `--quick` - Skip database volume sizing for faster results

**Output includes**:
- Instance 1 Storage table
- Instance 1 CPU/Usage table
- Instance 2 Storage table
- Instance 2 CPU/Usage table
- Summary comparison table

**Sample Output**:
```
FLEET EC2 Dashboard
Generated: 2025-12-09 14:45:00

━━━ Instance 1 - STORAGE (203.0.113.10) ━━━

| Category | Total | Used | Available | Usage |
|----------|-------|------|-----------|-------|
| Disk | 194G | 97G | 97G | 50% |
| FLEET Directory | - | 45G | - | - |
| Shared venv | - | 5.5G | - | - |

**Database Volumes:**
| Project | Type | Size |
|---------|------|------|
| atlas | DB | 80.7M |
| hermes | TimescaleDB | 70.9M |

━━━ Instance 1 - CPU/USAGE (203.0.113.10) ━━━

| Metric | Value |
|--------|-------|
| Load Average | 10.77, 13.19, 15.50 |
| CPU Usage | 92.4% |
| Memory | 6.7Gi/15Gi (44.7%) |
| Claude Sessions | 16 |
| Docker Containers | 20 |

... (Instance 2 tables follow)

━━━ SUMMARY COMPARISON ━━━

| Metric | Instance 1 | Instance 2 |
|--------|------------|------------|
| Disk Usage | 50% | 28% |
| CPU Usage | 92.4% | 40% |
| Claude Sessions | 16 | 12 |
| Docker Containers | 20 | 0 |
```

---

### sysmon projects

Project-based metrics dashboard showing containers, database volumes, and disk usage organized by project.

```bash
sysmon projects                    # All projects, both instances
sysmon projects --instance 1       # Projects on Instance 1 only
sysmon projects --instance 2       # Projects on Instance 2 only
sysmon projects --project atlas # Detailed view of single project
sysmon projects --quick            # Skip DB volume sizing
```

**Options**:
- `--instance <n>` - Show projects for specific instance (1 or 2)
- `--project <name>` - Show detailed metrics for a single project
- `--quick` - Skip database volume sizing for faster results

**Project List by Instance**:
- **Instance 1**: vega, altair, atlas, hermes, orion, polaris, sirius, lyra
- **Instance 2**: nova, quasar, pulsar, cygnus, draco, phoenix, aquila, carina

**Sample Output (Summary)**:
```
━━━ Instance 1 Projects (203.0.113.10) ━━━

| Project | Containers | DB Volume | Disk Usage | Status |
|---------|------------|-----------|------------|--------|
| atlas | 3 | 80.7M (PostgreSQL) | 2.1G | running |
| hermes | 2 | 70.9M (TimescaleDB) | 1.8G | running |
| orion | 2 | 66.8M (PostgreSQL) | 1.5G | running |
| lyra | 0 | - | 674M | stopped |
...

━━━ PROJECT SUMMARY ━━━

| Instance | Total Projects | Running | Stopped |
|----------|----------------|---------|---------|
| Instance 1 | 8 | 5 | 3 |
| Instance 2 | 8 | 0 | 8 |
```

**Sample Output (Single Project)**:
```
━━━ Project: atlas (Instance 1 - 203.0.113.10) ━━━

**Overview:**
| Metric | Value |
|--------|-------|
| Disk Usage | 2.1G |
| Running Containers | 3 |
| Database | PostgreSQL (80.7M) |

**Containers:**
| Name | Status |
|------|--------|
| atlas-api | Up 2 hours |
| atlas-worker | Up 2 hours |
| atlas-postgres | Up 2 hours (healthy) |
```

---

### sysmon cleanup docker

Safe Docker cleanup with interactive confirmations.

```bash
sysmon cleanup docker              # Interactive cleanup
sysmon cleanup docker --yes        # Auto-confirm
sysmon cleanup docker --aggressive # Full cleanup
```

**Options**:
- `--yes, -y` - Skip confirmation prompts
- `--aggressive` - Remove ALL unused images and volumes (not just dangling)

**Cleanup phases (standard)**:
1. Dangling images (tagged as `<none>`)
2. Stopped containers (status=exited)
3. Build cache

**Additional with --aggressive**:
4. All unused images
5. Unused volumes (DATA LOSS WARNING)

**Expected recovery**:
- Standard: 10-30GB
- Aggressive: 30-50GB+

---

### sysmon cleanup builds

Build artifact cleanup for FLEET projects.

```bash
sysmon cleanup builds                        # Standard cleanup
sysmon cleanup builds --yes                  # Auto-confirm
sysmon cleanup builds --include-rust         # Include Rust targets (30GB+)
sysmon cleanup builds --include-node-modules # Include node_modules
sysmon cleanup builds --path /custom/path    # Custom base path
```

**Options**:
- `--include-rust` - Also remove Rust target directories (requires cargo build to restore)
- `--include-node-modules` - Also remove node_modules (requires npm install to restore)
- `--path <dir>` - Base path to clean (default: ~/fleet)
- `--yes, -y` - Skip confirmation prompts

**Cleanup targets**:
1. `.next` directories (Next.js build output)
2. `build` directories (generic build output)
3. `dist` directories (distribution builds)
4. `__pycache__` directories (Python cache)
5. `target` directories (with --include-rust flag) - Rust build artifacts
6. `node_modules` (with --include-node-modules flag)

**Expected recovery**:
- .next: 3-5GB
- Rust target: **20-40GB** (lyra, sirius, etc.)
- node_modules: 5-15GB
- __pycache__: <100MB

---

### sysmon cleanup caches

System cache cleanup (npm, cargo, Claude Code).

```bash
sysmon cleanup caches              # Clean all caches (interactive)
sysmon cleanup caches --npm        # Clean only npm cache
sysmon cleanup caches --cargo      # Clean only cargo cache
sysmon cleanup caches --claude     # Clean only Claude cache
sysmon cleanup caches --all --yes  # Clean all, auto-confirm
```

**Options**:
- `--npm` - Clean npm cache (~/.npm and /root/.npm)
- `--cargo` - Clean cargo registry cache (~/.cargo/registry, ~/.cargo/git)
- `--claude` - Clean Claude Code cache (~/.claude)
- `--all` - Clean all caches (default if no specific flag)
- `--yes, -y` - Skip confirmation prompts

**Cache locations**:
| Cache | Location | Typical Size |
|-------|----------|--------------|
| npm | ~/.npm, /root/.npm | 3-5GB |
| cargo | ~/.cargo/registry, ~/.cargo/git | 1-3GB |
| claude | ~/.claude | 1-2GB |

**Note**: Cleaning caches is safe - they will be rebuilt automatically when needed.

---

### sysmon cleanup preserves

Backup/preserve cleanup with retention policy.

```bash
sysmon cleanup preserves              # Keep 3 most recent
sysmon cleanup preserves --keep 5     # Keep 5 most recent
sysmon cleanup preserves --all        # Remove ALL preserves
sysmon cleanup preserves --yes        # Auto-confirm
```

**Options**:
- `--keep <n>` - Keep the N most recent preserves (default: 3)
- `--path <dir>` - Preserve directory path (default: ~/fleet-preserves)
- `--all` - Remove ALL preserves (use with caution)
- `--yes, -y` - Skip confirmation prompts

**Default behavior**: Keeps the 3 most recent preserves and removes older ones.

**Preserve location**: `~/fleet-preserves`
**Created by**: `sega/engine/sega/system/preserve/create-ecosystem-preserve.sh`

---

### sysmon report

Generate structured reports in markdown or JSON format.

```bash
sysmon report                       # Markdown to stdout
sysmon report --format json         # JSON output
sysmon report --output report.md    # Save to file
sysmon report --all                 # Include all instances
```

**Options**:
- `--format <fmt>` - Output format: markdown (default) or json
- `--output <file>` - Save to file instead of stdout
- `--all` - Include remote instance metrics

---

## Global Options

All commands support these global options:

| Option | Description |
|--------|-------------|
| `--help, -h` | Show help |
| `--version, -v` | Show version |
| `--dry-run` | Show what would be done without executing |
| `--verbose` | Enable verbose output |
| `--quiet, -q` | Suppress non-essential output |

---

## Configuration

Environment variables can override defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `SYSMON_SSH_KEY` | *(none — injected from `[instances]` in `config/sega.toml` via the sega CLI)* | SSH key path (e.g. `~/.ssh/my-key.pem`) |
| `SYSMON_INSTANCE1_IP` | *(none — injected from `config/sega.toml`)* | Instance 1 IP (e.g. `203.0.113.10`) |
| `SYSMON_INSTANCE2_IP` | *(none — injected from `config/sega.toml`)* | Instance 2 IP (e.g. `203.0.113.20`) |
| `SYSMON_DISK_WARNING` | `75` | Disk warning threshold % |
| `SYSMON_DISK_CRITICAL` | `90` | Disk critical threshold % |
| `SYSMON_CPU_WARNING` | `70` | CPU warning threshold % |
| `SYSMON_CPU_CRITICAL` | `90` | CPU critical threshold % |
| `SYSMON_MEM_WARNING` | `80` | Memory warning threshold % |
| `SYSMON_MEM_CRITICAL` | `95` | Memory critical threshold % |
| `SYSMON_DRY_RUN` | `false` | Enable dry-run mode |
| `SYSMON_VERBOSE` | `false` | Enable verbose mode |
| `SYSMON_QUIET` | `false` | Enable quiet mode |

---

## Recommended Workflows

### Daily Quick Check

```bash
sysmon status --all
```

### Monthly Disk Maintenance

```bash
# 1. Check current state
sysmon analyze --with-cpu

# 2. Review recommendations in output

# 3. Clean build artifacts (safe)
sysmon cleanup builds

# 4. Clean Docker if needed
sysmon cleanup docker
```

### Emergency Cleanup (>90% disk)

```bash
# 1. Immediate safe cleanup (standard build artifacts)
sysmon cleanup builds
sysmon cleanup docker

# 2. Clean system caches (npm, cargo) - safe, auto-rebuilds
sysmon cleanup caches --yes

# 3. Clean Rust targets - BIG savings (20-40GB)
sysmon cleanup builds --include-rust --yes

# 4. Clean old preserves/backups
sysmon cleanup preserves --yes

# 5. If still critical, include node_modules
sysmon cleanup builds --include-node-modules

# 6. If still critical, aggressive Docker
sysmon cleanup docker --aggressive
```

### Multi-Instance Monitoring

```bash
# Full dashboard view
sysmon dashboard

# Quick check (skip DB sizing)
sysmon dashboard --quick

# Generate report for documentation
sysmon report --all --output /tmp/system-report.md
```

---

## Architecture

```
sega/engine/sega/system/sysmon/
├── sysmon                      # Main dispatcher
├── lib/
│   ├── common.sh               # Colors, logging, utilities
│   ├── config.sh               # Instance IPs, paths, thresholds
│   └── collectors.sh           # Data collection functions
├── commands/
│   ├── status.sh               # Quick status command
│   ├── analyze.sh              # Deep analysis command
│   ├── dashboard.sh            # Multi-instance dashboard
│   ├── projects.sh             # Project-based metrics
│   ├── cleanup-docker.sh       # Docker cleanup
│   ├── cleanup-builds.sh       # Build artifact cleanup (+ Rust)
│   ├── cleanup-caches.sh       # System cache cleanup (npm/cargo/claude)
│   ├── cleanup-preserves.sh    # Backup/preserve cleanup
│   └── report.sh               # Report generation
└── README.md                   # This file
```

---

## Integration

### Related Scripts (SEGA System Modules)
- `/sega/engine/sega/system/preserve/create-ecosystem-preserve.sh` - Create backups before cleanup
- `/sega/engine/sega/system/sysnc/bulk-stash-pull-pop-push.sh` - Multi-instance sync
- `/sega/engine/sega/system/sysnc/gitlab-verify-sync.sh` - Verify 3-system consistency

### Referenced In
- `/docs/guides/procedures/WORKFLOW_ORCHESTRATION.md` - Repository maintenance
- `/docs/operations/infrastructure/EC2_INSTANCE_REGISTRY.md` - Instance management
- `/dispatcher/CLAUDE.md` - Operations context

---

## Troubleshooting

### "Permission denied" errors
- Docker commands may require `sudo`
- Some system directories require elevated permissions

### SSH connection failures
- Check SSH key exists: `ls ~/.ssh/my-key.pem`
- Test connectivity: `ssh -i ~/.ssh/my-key.pem ubuntu@203.0.113.10 echo ok`
- Verify network access to EC2 instances

### Command not found
```bash
# Option 1: Use full path
~/fleet/sega/engine/sega/system/sysmon/sysmon status

# Option 2: Add to PATH
export PATH="$PATH:$HOME/fleet/sega/engine/sega/system/sysmon"

# Option 3: Use SEGA CLI
sega sysmon status
```

---

**Version**: 1.0.0
**Last Updated**: 2025-12-09
**Maintainer**: Operations Division
