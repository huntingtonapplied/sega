# SEGA Preserve Module

Ecosystem backup and recovery tools for the FLEET ecosystem.

## Purpose

The preserve module provides backup functionality that should be run before sync operations. It creates timestamped, compressed backups of the entire FLEET ecosystem with intelligent exclusions.

## Scripts

### create-ecosystem-preserve.sh

Creates a comprehensive backup of the FLEET ecosystem.

**Features**:
- Timestamped backups (e.g., `fleet_preserve_20251216_143022.tar.gz`)
- 50+ exclusion patterns (node_modules, .git, __pycache__, etc.)
- Compression with gzip
- Size reporting

**Usage**:
```bash
# Direct execution
./create-ecosystem-preserve.sh

# Via SEGA CLI (planned)
sega preserve
```

## CLI Commands (Planned)

```bash
sega preserve                     # Create timestamped backup
sega preserve --list              # List existing preserves
sega preserve --cleanup [--keep N] # Remove old preserves, keep N most recent
sega preserve --size              # Show preserve directory size
```

## Integration with sysnc

The preserve module works in conjunction with the sysnc module:

```bash
# Recommended workflow
sega preserve                     # Backup first
sega sysnc run                    # Then sync

# Or combined (planned)
sega sysnc run --auto-preserve    # Backup + sync in one command
```

## Backup Location

Backups are stored in the user's home directory:
```
~/fleet_preserve_YYYYMMDD_HHMMSS.tar.gz
```

## Related

- [Sysnc Module](../sysnc/README.md) - Git synchronization tools
- [Sysmon Module](../sysmon/README.md) - System monitoring tools
