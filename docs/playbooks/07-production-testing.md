# 07: Production Testing

Validate production deployments.

> **Detailed Procedure**: See [TESTING_PROCEDURE.md](../reference/TESTING_PROCEDURE.md) for all testing levels and command options.

## Smoke Tests

```bash
# Quick health verification
curl https://<domain>/health
curl https://<domain>/api/health

# Service status
sega ship status --target production
```

## Integration Verification

```bash
# Run production integration tests
sega probe integration --target production

# API validation
sega probe api --base-url https://<domain>/api
```

## Performance Testing

```bash
# Run benchmarks
sega probe benchmark --target production

# Load testing (if configured)
sega probe load --target production --users 100
```

## Security Scanning

```bash
# Dependency vulnerabilities
sega doctor scan --type deps

# Secrets exposure check
sega doctor scan --type secrets

# Full security scan
sega doctor scan --type security
```

## Monitoring Verification

```bash
# Check metrics flowing
sega sysmon status --all

# Verify logging
sega logs --target production --tail 50

# Dashboard check
sega sysmon dashboard
```

## Validation Sequence

```bash
# 1. Health checks
curl https://<domain>/health

# 2. Smoke tests
sega probe run --type smoke --target production

# 3. Integration tests
sega probe integration --target production

# 4. Security scan
sega doctor scan --type security

# 5. Monitor
sega sysmon dashboard
```

## Incident Response

```bash
# Quick diagnostics
sega doctor diagnose --all

# View recent logs
sega logs --target production --tail 100

# Rollback if needed
sega ship rollback --steps 1
```
