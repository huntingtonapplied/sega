# Comprehensive Domain Testing Infrastructure

**Status**: ✅ COMPLETE (2026-01-05)  
**SEGA Version**: 1.0  
**Purpose**: Test both localhost (via SSH) and production domains for all portfolio projects

---

## Overview

This infrastructure provides comprehensive testing for all portfolio projects across your EC2 instances, addressing the critical requirement that **EC2 security groups don't expose landing (3xxx) and product_app (4xxx) ports externally**.

### Testing Capabilities

1. **Localhost Testing (SSH-based)**: Test endpoints on EC2 instances that aren't externally accessible
2. **Production Domain Testing**: Test publicly accessible production domains with SSL validation
3. **Comprehensive Testing**: Combine both localhost and production testing in a single run

---

## Architecture

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **SSH Utility** | `engine/sega/utils/ssh.py` | Remote command execution via SSH |
| **Instance Test Runner** | `engine/sega/probe/instance_test_runner.py` | Localhost testing via SSH |
| **Domain Test Runner** | `engine/sega/probe/domain_test_runner.py` | Production domain testing (enhanced) |
| **Probe Commands** | `engine/sega/cli/commands/probe.py` | CLI commands (enhanced) |
| **Domain Registry** | `config/domain_registry.yaml` | Project/instance/port mappings |

### Key Infrastructure Details

```yaml
Instances:
  - prod-instance-01 (203.0.113.11): Groups 1 + 4 (11 projects)
  - prod-instance-02 (203.0.113.12): Group 2 (4 projects)
  - prod-instance-03 (203.0.113.13): Group 3 (5 projects)
  - prod-instance-04 (203.0.113.11): Group 4 (temporary, using Instance 1 IP)

Port Allocation:
  - Landing: 3000 + project_id
  - Product App: 4000 + project_id
  - API: 8000 + project_id

Domain Patterns:
  - Landing: {project}.{tld} (e.g., service-b.example.com)
  - Product App: app.{project}.{tld} (e.g., app.service-b.example.com)
  - API: api.{project}.{tld} (e.g., api.service-b.example.com)
  - Staging: staging.{production-domain} (e.g., staging.service-b.example.com)
```

---

## Commands

### 1. Test Localhost on EC2 Instances

```bash
# Test all instances (SSH into each and test localhost endpoints)
sega probe instance

# Test specific instance
sega probe instance --instance 1

# Test multiple instances
sega probe instance --instance 1 --instance 2

# Verbose output
sega probe instance --verbose

# JSON output
sega probe instance --json-output

# Custom SSH key
sega probe instance --ssh-key ~/custom-key.pem
```

**What it tests:**
- SSH into each instance
- Test `localhost:3xxx` (landing pages)
- Test `localhost:4xxx` (product apps)
- Test `localhost:8xxx/health` (API health endpoints)

**Example output:**
```
================================================================================
INSTANCE LOCALHOST TEST RESULTS
================================================================================

prod-instance-01 [PASS] (203.0.113.11)
  SSH: connected
  Tests: 18/18 passed
  Duration: 2.45s

  [OK] service-a
      [OK] landing (:3004): 200 (145ms)
      [OK] product_app (:4004): 200 (132ms)
      [OK] api (:8004): 200 (98ms)

  [OK] service-d
      [OK] landing (:3005): 200 (156ms)
      [OK] product_app (:4005): 200 (141ms)
      [OK] api (:8005): 200 (102ms)
...
```

---

### 2. Test Production Domains

```bash
# Test all production domains (existing behavior)
sega probe domain

# Test specific project
sega probe domain -p service-b

# Test multiple projects
sega probe domain -p service-b -p service-c -p service-a

# Test specific instance projects
sega probe domain --instance 1

# Test only landing pages
sega probe domain --type landing

# Test only APIs
sega probe domain --type api

# Disable SSL verification (for testing)
sega probe domain --no-ssl

# Production domains only
sega probe domain --domain production
```

**What it tests:**
- Production domain URLs (e.g., `https://service-b.example.com`)
- SSL certificate validity
- Response status codes
- Response times

---

### 3. Comprehensive Testing (Localhost + Production)

```bash
# Test BOTH localhost (via SSH) and production domains
sega probe domain --test-localhost

# Comprehensive test for specific instance
sega probe domain --instance 1 --test-localhost

# Comprehensive test for specific projects
sega probe domain -p service-a -p service-b --test-localhost

# Comprehensive with custom SSH key
sega probe domain --test-localhost --ssh-key ~/custom.pem

# Production domains + localhost, no internal
sega probe domain --test-localhost --domain production
```

**What it tests:**
1. SSH into EC2 instances → Test localhost endpoints
2. Test production domain URLs
3. Combined report showing both

**Example output:**
```
================================================================================
COMPREHENSIVE DOMAIN TEST RESULTS
================================================================================

service-a [PASS] (prod-instance-01)
  Tests: 6/6 passed
  Duration: 2.34s

  Localhost (via SSH):
    [OK] landing (:3004): 200 (145ms)
    [OK] product_app (:4004): 200 (132ms)
    [OK] api (:8004): 200 (98ms)

  Production Domains:
    [OK] production/landing: 200 (256ms) (SSL: valid, 89d)
    [OK] production/product_app: 200 (243ms) (SSL: valid, 89d)
    [OK] production/api: 200 (198ms) (SSL: valid, 89d)
...
SUMMARY: 20/20 projects passed, 120/120 tests passed
  Localhost: 60 tests | Production: 60 tests
```

---

## Use Cases

### Daily Health Checks

Check if all services are running on all instances:

```bash
# Quick localhost check (are services running?)
sega probe instance

# Full health check (localhost + production)
sega probe domain --test-localhost
```

### Deployment Verification

After deploying to an instance, verify everything works:

```bash
# Check Instance 1 after deployment
sega probe instance --instance 1 --verbose

# Comprehensive check for Instance 1
sega probe domain --instance 1 --test-localhost
```

### Project-Specific Testing

Test specific projects across all environments:

```bash
# Test Service-a everywhere
sega probe domain -p service-a --test-localhost

# Test multiple projects
sega probe domain -p service-a -p service-b -p service-c --test-localhost
```

### Debugging

```bash
# Verbose SSH debugging
sega probe instance --instance 1 --verbose

# Test with no SSL verification
sega probe domain --no-ssl

# JSON output for automation
sega probe instance --json-output > results.json
```

---

## Configuration

### Domain Registry: `config/domain_registry.yaml`

Complete configuration for all projects:

```yaml
projects:
  service-a:
    id: 4
    instance: "prod-instance-01"
    group: 1
    domains:
      production: "service-a.example.com"
      internal: "staging.service-a.example.com"
    endpoints:
      landing:
        port: 3004
        path: "/"
        expected_status: [200]
      product_app:
        port: 4004
        path: "/"
        expected_status: [200, 302]
      api:
        port: 8004
        path: "/health"
        expected_status: [200]
```

### SSH Configuration

Default SSH key: `~/your-key.pem`  
Default user: `ubuntu`  
Timeout: 10 seconds (configurable)

Override with:
```bash
sega probe instance --ssh-key ~/custom.pem --timeout 30
```

---

## Technical Details

### SSH Execution Flow

1. **Connect**: SSH to instance using private key
2. **Execute**: Run `curl -s -w '\n%{http_code}' -m 10 'http://localhost:PORT/PATH'`
3. **Parse**: Extract HTTP status code and response body
4. **Report**: Return success/failure with timing

### Security

- SSH keys required (no password authentication)
- StrictHostKeyChecking disabled for automation
- UserKnownHostsFile disabled (ephemeral instances)
- Connection timeout enforced
- All traffic encrypted via SSH tunnel

### Error Handling

- SSH connection failures: Reported per instance
- Timeout handling: Configurable per request
- Port unreachable: Detected and reported
- SSL errors: Captured and displayed

---

## Project Coverage

### Instance 1 (prod-instance-01) - 11 Projects
- **Group 1**: service-a, service-d, service-e, service-f, service-r, service-s
- **Group 4** (temporary): Service-g, Service-h, Service-i, Service-j, Service-c

### Instance 2 (prod-instance-02) - 4 Projects
- Service-b, Service-k, Service-l, Service-m

### Instance 3 (prod-instance-03) - 5 Projects
- service-n, service-o, service-p, service-q, service-t

### Instance 4 (prod-instance-04) - Future
- Currently using Instance 1 IP (temporary)

---

## Integration with Existing Commands

### Relationship to `sega health`

```bash
# sega health - Tests externally accessible endpoints
sega health --project service-a --host 203.0.113.11
# ❌ Fails - port 8004 not exposed externally

# sega probe instance - Tests via SSH
sega probe instance --instance 1
# ✅ Works - SSH tunnels to localhost
```

### Relationship to existing `sega probe domain`

**Before Enhancement:**
- Only tested production/internal domain URLs
- No localhost testing capability

**After Enhancement:**
- `sega probe domain` - Original behavior (production domains only)
- `sega probe domain --test-localhost` - Enhanced (localhost + production)
- `sega probe instance` - New command (localhost only)

---

## Troubleshooting

### SSH Connection Issues

```bash
# Verify SSH key exists
ls -l ~/your-key.pem

# Test SSH manually
ssh -i ~/your-key.pem ubuntu@203.0.113.11

# Check SEGA SSH connection
sega probe instance --instance 1 --verbose
```

### Timeout Issues

```bash
# Increase timeout for slow connections
sega probe instance --timeout 30

# Test specific instance
sega probe instance --instance 1 --timeout 30 --verbose
```

### Missing Configuration

```bash
# Verify domain registry exists
cat config/domain_registry.yaml

# Check project is configured
grep -A 20 "service-a:" config/domain_registry.yaml
```

---

## Future Enhancements

- [ ] Parallel instance testing (currently sequential)
- [ ] Custom health check endpoints per project
- [ ] Historical test result tracking
- [ ] Alerting on test failures
- [ ] Integration with CI/CD pipelines
- [ ] Instance 4 migration when IP assigned

---

## References

- **Domain Registry**: `docs/architecture/infrastructure/dns/DOMAIN_REGISTRY.md`
- **Port Standards**: `docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md`
- **NGINX Deployment**: `docs/operations/UNIFIED_SERVER_DEPLOYMENT.md`
- **Project Health Checks**: `docs/guides/procedures/PROJECT_HEALTH_CHECK_PROCEDURE.md`

---

**Created**: 2026-01-05  
**Author**: SEGA Infrastructure Team  
**Last Updated**: 2026-01-05  
**Version**: 1.0
