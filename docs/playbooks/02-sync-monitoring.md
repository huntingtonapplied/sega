# 02: Sync & Monitoring

Multi-system synchronization and infrastructure monitoring.

## System Monitoring (sysmon)

```bash
# Quick status check
sega sysmon status --all

# Deep analysis with recommendations
sega sysmon analyze --with-cpu

# Multi-instance dashboard
sega sysmon dashboard

# Cleanup operations
sega sysmon cleanup docker    # Dangling images, build cache
sega sysmon cleanup builds    # .next, dist, __pycache__

# Generate report
sega sysmon report --format json
```

## Git Synchronization (sysnc)

3-system architecture: Local → EC2-1 → EC2-2

```bash
# 1. Inspect changes across all systems
sega sysnc inspect --enhanced

# 2. Analyze for conflicts
sega sysnc analyze

# 3. Preview sync (dry run)
sega sysnc run --dry-run

# 4. Execute sync
sega sysnc run

# 5. Bulk operations (all projects)
sega sysnc bulk --all
```

## Regular Maintenance Cycle

```bash
# Daily
sega sysmon status --all
sega sysnc inspect

# Weekly
sega sysmon analyze --with-cpu
sega sysmon cleanup docker

# Before releases
sega sysnc run
sega sysmon report
```
