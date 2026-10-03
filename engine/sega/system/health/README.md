# SEGA Health Check Utilities

System utilities for checking health of FLEET projects across EC2 instances.

## Testing Pipeline

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Phase 1:       │     │  Phase 2:       │     │  Phase 3:       │
│  Health Check   │────▶│  API Testing    │────▶│  Browser Tests  │
│  (sega health)  │     │  (sega test-api)│     │  (sega test     │
│                 │     │                 │     │   browser)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Scripts

### full-test-pipeline.sh

Runs the complete testing pipeline: Health → API → Browser tests.

**Usage:**
```bash
# Full pipeline on Instance 2
./full-test-pipeline.sh

# Full pipeline on Instance 1
./full-test-pipeline.sh --instance 1

# Test specific project
./full-test-pipeline.sh --project hermes

# Quick mode (health + API health only)
./full-test-pipeline.sh --quick

# Skip browser tests
./full-test-pipeline.sh --skip-browser
```

### ec2-health-check.sh

Comprehensive health survey of FLEET projects on EC2 instances.

**Usage:**
```bash
# Check Instance 2 (default)
./ec2-health-check.sh

# Check Instance 1
./ec2-health-check.sh --instance 1

# Check specific project
./ec2-health-check.sh --project hermes

# Quick check (skip port survey)
./ec2-health-check.sh --quick

# JSON output
./ec2-health-check.sh --json
```

**What it checks:**
1. **Port Survey** - All listening ports (ss -tlnp)
2. **Docker Containers** - Running containers and their ports
3. **Nginx Status** - Configuration validation
4. **Service Health** - API health endpoints via `sega health`

## Health Check Methods

### SSH Method (Recommended for EC2)
The `ec2-health-check.sh` script uses SSH to run health checks on the remote instance. This works regardless of EC2 security group settings because checks run locally on the instance.

```bash
./ec2-health-check.sh --instance 2
```

### Direct Method (Requires Open Ports)
`sega health --host <IP>` connects directly to the IP:PORT. This requires:
- Port 8xxx open in EC2 security groups, OR
- VPN connection to the instance, OR
- Local development (`--host localhost`)

```bash
# Only works if ports are open
sega health --all-services --host 203.0.113.20
```

> **Note**: EC2 security groups typically only expose port 80 (nginx).
> Use the SSH method for standard EC2 deployments.

## Related Documentation

- [PROJECT_HEALTH_CHECK_PROCEDURE.md](/docs/guides/procedures/PROJECT_HEALTH_CHECK_PROCEDURE.md) - Full procedure documentation
- [PORT_ALLOCATION_STANDARDS.md](/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md) - Authoritative port assignments
- [FLEET_DOMAIN_REGISTRY.md](/docs/architecture/infrastructure/dns/FLEET_DOMAIN_REGISTRY.md) - Domain mappings

## Instance Configuration

Instance IPs and project groups come from `[instances]` in `config/sega.toml`
(or the `SYSMON_INSTANCE<N>_IP` / `SYSMON_INSTANCE<N>_PROJECTS` environment
variables). Example:

| Instance | IP | Projects |
|----------|-----|----------|
| 1 | 203.0.113.10 | atlas, hermes, orion |
| 2 | 203.0.113.20 | lyra, vega, altair |

## Environment Variables

- `SSH_KEY` - Path to SSH key (required; e.g. `~/.ssh/my-key.pem`, or configure `[instances]` in `config/sega.toml`)

## SEGA CLI Integration

The script leverages `sega health` for service health checks:

```bash
# Used by the script
sega health --all-services --host <IP>
sega health --project <name> --host <IP>
```

See `sega health --help` for all options.
