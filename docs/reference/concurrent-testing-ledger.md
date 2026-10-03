# Concurrent Testing with Project Ledger

**Version**: 1.0
**Created**: 2025-10-06
**Purpose**: Enable multiple agents to test your projects concurrently without conflicts
**Authority**: SEGA Infrastructure Division

## Overview

The SEGA Project Ledger provides a file-based locking system that coordinates concurrent testing across multiple agents. This prevents port conflicts, resource contention, and race conditions when multiple agents are testing different projects simultaneously.

## Problem Statement

When running parallel testing across the whole portfolio:

1. **Port Conflicts**: Multiple projects trying to use the same ports (8000-8099, 3000-3099, etc.)
2. **Resource Contention**: Docker services, databases, and caches conflicting
3. **Race Conditions**: Agents starting/stopping services simultaneously
4. **Testing Chaos**: No visibility into which agent is testing which project

## Solution: Project Reservation Ledger

The ledger provides:
- **Atomic Locking**: File-based locks using `fcntl` for mutual exclusion
- **Automatic Expiration**: Stale reservations auto-release after 30 minutes
- **Port Conflict Detection**: Prevents reserving projects with overlapping ports
- **History Tracking**: Complete audit trail of all reservations
- **CLI Management**: Monitor and manage reservations via `sega ledger` commands

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Agent 001  │     │  Agent 002  │     │  Agent 003  │
│  Testing    │     │  Testing    │     │  Testing    │
│  service-a  │     │  service-b  │     │  service-c  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────┐
│            Project Reservation Ledger               │
│            ~/.sega/project_ledger.json              │
│                                                     │
│  {                                                  │
│    "reservations": {                               │
│      "service-a": {                                 │
│        "agent_id": "agent-001",                   │
│        "reserved_at": "2025-10-06T12:00:00",      │
│        "expires_at": "2025-10-06T12:30:00",       │
│        "ports_used": [8000, 3000, 5000, 6000]     │
│      },                                            │
│      "service-b": {...},                              │
│      "service-c": {...}                                │
│    },                                              │
│    "history": [...]                                │
│  }                                                  │
└─────────────────────────────────────────────────────┘
```

## Usage

### Basic Workflow

```bash
# Agent 001: Test service-a
sega local up -p service-a --agent-id agent-001

# Agent 002: Test service-b (concurrent with agent-001)
sega local up -p service-b --agent-id agent-002

# Agent 003: Try to test service-a (will be skipped - reserved by agent-001)
sega local up -p service-a --agent-id agent-003
# Output: [SKIP] service-a - Reserved by agent-001 (since 2025-10-06 12:00:00)
```

### Automatic Agent ID

If you don't provide `--agent-id`, SEGA auto-generates one based on process ID:

```bash
# Auto-generated agent ID: pid-12345
sega local up -p service-a
```

### Disable Ledger (Single Agent)

For single-agent testing or debugging:

```bash
sega local up -p service-a --no-ledger
```

### Check Reservation Status

```bash
# Show all active reservations
sega ledger status

# Output:
# ╔═══════════╦══════════════╦═══════════════════════╦═══════════════════════╦══════════╦═══════╦═══════════════════╗
# ║ Project   ║ Agent ID     ║ Reserved At           ║ Expires At            ║ Status   ║ PID   ║ Ports             ║
# ╠═══════════╬══════════════╬═══════════════════════╬═══════════════════════╬══════════╬═══════╬═══════════════════╣
# ║ service-a ║ agent-001    ║ 2025-10-06 12:00:00   ║ 2025-10-06 12:30:00   ║ active   ║ 12345 ║ 8000,3000,5000... ║
# ║ service-b ║ agent-002    ║ 2025-10-06 12:05:00   ║ 2025-10-06 12:35:00   ║ active   ║ 12346 ║ 8001,3001,5001... ║
# ╚═══════════╩══════════════╩═══════════════════════╩═══════════════════════╩══════════╩═══════╩═══════════════════╝

# Check if specific project is available
sega ledger check service-a
# Output: [BUSY] service-a is reserved by agent-001
```

### View Reservation History

```bash
# Show last 20 reservation entries
sega ledger history

# Show history for specific project
sega ledger history -p service-a

# Show last 50 entries
sega ledger history -n 50
```

### Force Release (Admin Override)

```bash
# Force release a stuck reservation
sega ledger release service-a --force
```

### Cleanup Expired Reservations

```bash
# Preview what would be cleaned
sega ledger cleanup --dry-run

# Clean up expired reservations
sega ledger cleanup
```

## Implementation Details

### File-Based Locking

The ledger uses `fcntl.flock()` for atomic file locking:

```python
# Acquiring lock blocks until available
with self._lock_ledger():
    # Critical section - only one process can be here
    ledger = self._read_ledger()
    # ... modify ledger ...
    self._write_ledger(ledger)
# Lock automatically released
```

### Automatic Expiration

Reservations expire after 30 minutes (configurable):

```python
ledger = ProjectLedger(timeout_minutes=60)  # 60 minute timeout
```

Expired reservations are automatically cleaned up when:
- Checking project availability
- Listing active reservations
- Running `sega ledger cleanup`

### Port Conflict Detection

The ledger tracks ports used by each project:

```python
# service-a uses: 8000, 3000, 5000, 6000
ledger.acquire('service-a', 'agent-001', ports=[8000, 3000, 5000, 6000])

# service-c uses: 8002, 3002, 5002, 6002 (no conflict)
ledger.acquire('service-c', 'agent-002', ports=[8002, 3002, 5002, 6002])  # OK

# Another agent tries to acquire service-a (port conflict)
ledger.acquire('service-a', 'agent-003')  # BLOCKED - already reserved
```

## Integration with sega local

### Modified Deployment Flow

```python
# Old behavior (no coordination)
sega local up -p service-a
# Always tries to deploy, potential conflicts

# New behavior (with ledger)
sega local up -p service-a --agent-id agent-001
# 1. Check if service-a is available
# 2. Acquire reservation (atomic lock)
# 3. Deploy project
# 4. Release reservation on success/failure
```

### Parallel Testing Example

```bash
# Terminal 1: Agent testing web projects
sega local up -p service-a -p service-b -p service-c --agent-id web-tester

# Terminal 2: Agent testing backend projects
sega local up -p service-d -p web-app --agent-id backend-tester

# Terminal 3: Agent testing infrastructure
sega local up -p service-e -p sega --agent-id infra-tester

# All three agents run concurrently without conflicts
```

## Best Practices

### 1. Use Meaningful Agent IDs

```bash
# Good: Descriptive agent IDs
sega local up -p service-a --agent-id ci-pipeline-001
sega local up -p service-b --agent-id dev-machine-alice
sega local up -p service-c --agent-id automated-tester-beta

# Less useful: Generic IDs
sega local up -p service-a --agent-id agent-1
```

### 2. Monitor Active Reservations

```bash
# Check before running tests
sega ledger status

# Clean up before major test runs
sega ledger cleanup
```

### 3. Handle Reservation Failures Gracefully

```bash
# In CI/CD pipeline
if ! sega local up -p service-a --agent-id ${CI_JOB_ID}; then
    echo "Project reserved or deployment failed - checking status"
    sega ledger check service-a
    exit 1
fi
```

### 4. Set Appropriate Timeouts

```bash
# For long-running integration tests
export SEGA_LEDGER_TIMEOUT=120  # 2 hours

# For quick unit tests
export SEGA_LEDGER_TIMEOUT=15   # 15 minutes
```

### 5. Force Release Only When Necessary

```bash
# Don't do this routinely
sega ledger release service-a --force

# Instead, clean up expired reservations
sega ledger cleanup

# Or check why it's still reserved
sega ledger status
sega ledger history -p service-a
```

## Troubleshooting

### Problem: "Project reserved by other agent"

**Symptom**:
```
[SKIP] service-a - Reserved by agent-001 (since 2025-10-06 12:00:00)
```

**Solutions**:
1. Wait for reservation to expire (default: 30 minutes)
2. Check if the other agent is actually testing: `ps aux | grep agent-001`
3. Force release if stuck: `sega ledger release service-a --force`
4. Clean up expired reservations: `sega ledger cleanup`

### Problem: Ledger file locked

**Symptom**:
```
Waiting for ledger lock...
```

**Cause**: Another process has the ledger file locked

**Solution**: Wait (lock released automatically), or check for hung processes

### Problem: Reservation not released

**Symptom**: Project shows reserved but no agent is testing

**Solutions**:
1. Check history: `sega ledger history -p service-a`
2. Check if process is still running: `ps aux | grep [PID]`
3. Force release: `sega ledger release service-a --force`

### Problem: Port conflicts despite ledger

**Symptom**: Port already in use error during deployment

**Cause**: Ports may not be tracked correctly

**Solution**: Update port tracking in deployment configuration

## Performance Characteristics

- **Lock Acquisition**: < 1ms (no contention), blocks if contention
- **Ledger Read/Write**: < 10ms (JSON serialization)
- **History Queries**: O(n) where n = history size (kept at 1000 max)
- **Cleanup**: O(n) where n = active reservations
- **Storage**: ~1KB per reservation, ~100KB for full history

## Security Considerations

### File Permissions

Ledger file location: `~/.sega/project_ledger.json`

Default permissions: `0644` (read/write for user, read for others)

For production:
```bash
# Restrict to single user
chmod 600 ~/.sega/project_ledger.json

# Or group-based access
chgrp ci-agents ~/.sega/project_ledger.json
chmod 660 ~/.sega/project_ledger.json
```

### PID Validation

The ledger stores process IDs but does **not** validate if processes are still running. This is by design to avoid race conditions.

To check if a reservation is valid:
```bash
RESERVATION=$(sega ledger status --format json | jq -r '.service-a.pid')
ps -p $RESERVATION || sega ledger release service-a --force
```

## API Reference

### Command Line Interface

```bash
# Deployment with ledger
sega local up [OPTIONS]
  --agent-id TEXT          Agent ID for concurrent testing
  --no-ledger              Skip project reservation ledger

# Ledger management
sega ledger status [--format {table|json|simple}]
sega ledger check PROJECT
sega ledger release PROJECT [--force]
sega ledger history [-p PROJECT] [-n LIMIT] [--format {table|json|simple}]
sega ledger cleanup [--dry-run]
```

### Python API

```python
from sega.core.project_ledger import ProjectLedger

# Initialize ledger
ledger = ProjectLedger()

# Acquire reservation
if ledger.acquire('service-a', 'agent-001', ports=[8000, 3000]):
    try:
        # Run tests
        run_service_a_tests()
    finally:
        # Always release
        ledger.release('service-a', 'agent-001', status='completed')

# Check availability
if ledger.is_available('service-b'):
    print("service-b is available")

# Get reservation info
reservation = ledger.get_reservation('service-c')
print(f"service-c reserved by: {reservation['agent_id']}")

# List all active
active = ledger.list_active_reservations()
for project, res in active.items():
    print(f"{project}: {res['agent_id']}")
```

## Future Enhancements

### Planned Features

1. **Distributed Ledger**: Redis-based locking for multi-machine coordination
2. **Priority Reservations**: CI/CD pipelines get priority over manual testing
3. **Reservation Queuing**: Wait for project to become available instead of failing
4. **Resource Budgeting**: Track CPU/memory usage per reservation
5. **Webhook Notifications**: Alert when reservations expire or fail
6. **Advanced Analytics**: Reservation patterns, bottleneck identification

### Migration Path

Current file-based ledger will remain default. Distributed ledger will be opt-in:

```bash
# Future: Distributed ledger via Redis
export SEGA_LEDGER_BACKEND=redis
export SEGA_LEDGER_REDIS_URL=redis://localhost:6379/0
sega local up -p service-a
```

## Related Documentation

- [PORT_ALLOCATION_STANDARDS.md](/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md) - Port allocation across your projects
- [SEGA_LOCAL_DEPLOYMENT_IMPROVEMENTS.md](/home/ubuntu/portfolio/sega/docs/enhancements/SEGA_LOCAL_DEPLOYMENT_IMPROVEMENTS_2025_10_03.md) - Local deployment UX enhancements
- [AWS_SECURITY_GROUP_CONFIGURATION.md](/home/ubuntu/portfolio/sega/docs/deployment/AWS_SECURITY_GROUP_CONFIGURATION.md) - Production port management

---

**File Reference**: `/home/ubuntu/portfolio/sega/docs/reference/concurrent-testing-ledger.md`
**Authority**: SEGA Infrastructure Division
**Status**: Production Ready
