# NGINX Check Integration Plan

**Date**: 2026-01-05
**Status**: PROPOSED
**Priority**: HIGH
**Affects**: Infrastructure monitoring, EC2 deployment validation

## Executive Summary

Integrate comprehensive nginx configuration and SSL certificate checking into SEGA CLI as `sega nginx check` command. This consolidates manual SSH inspection workflows into automated infrastructure validation accessible via CLI.

---

## Current State Analysis

### Existing SEGA Commands

SEGA already has infrastructure checking commands:

| Command | Purpose | File |
|---------|---------|------|
| `sega nginx` | Nginx management group | `engine/sega/cli/commands/nginx.py` |
| `sega nginx status-remote` | Basic remote nginx status | nginx.py:295 |
| `sega nginx deploy` | Deploy configs to instances | nginx.py:164 |
| `sega doctor` | Environment diagnostics | `engine/sega/cli/commands/doctor.py` |
| `sega health` | Service health checks | `engine/sega/cli/commands/health.py` |
| `sega probe` | Test orchestration | `engine/sega/cli/commands/probe.py` |

### Current Limitations

1. **`sega nginx status-remote`** (lines 292-345):
   - Only checks: nginx service status, config test result
   - **Missing**: SSL certificates, domain mappings, certbot auto-renewal
   - Basic output: just service status + config test line

2. **`sega doctor check`** (doctor.py:69-103):
   - Focuses on: local environment, tools, credentials
   - **Missing**: Remote EC2 infrastructure validation

3. **Manual workflow currently required**:
   ```bash
   # What we did manually:
   ssh instance "sudo nginx -t && systemctl status nginx"
   ssh instance "sudo ls /etc/letsencrypt/live/"
   ssh instance "sudo certbot certificates"
   ssh instance "sudo systemctl status certbot.timer"
   ssh instance "sudo grep 'server_name' /etc/nginx/sites-enabled/*.conf"
   ```

---

## Proposed Integration: `sega nginx check`

### Design Decision: Extend `sega nginx` Command Group

**Rationale**:
1. ✅ Natural fit - nginx operations already grouped under `sega nginx`
2. ✅ Consistent with existing `nginx status-remote`, `nginx deploy`
3. ✅ Follows SEGA principle: "Actions are commands, platforms are options"
4. ✅ Leverages existing EC2 infrastructure (ec2_config.py)

**Alternative Considered**: Add to `sega doctor`
- ❌ Doctor focuses on local environment diagnostics
- ❌ Would create inconsistency (nginx management split across commands)
- ✅ Could add `sega doctor nginx` as alias pointing to `sega nginx check`

### Command Structure

```bash
# Primary command
sega nginx check [OPTIONS]

# Options
--instance, -i <1|2|3|all>        # Instance to check (default: all)
--ssl                             # Check SSL certificates
--certbot                         # Check certbot auto-renewal
--domains                         # List configured domains
--detailed                        # Show full certificate details
--json                            # Output as JSON
--format <table|json|markdown>    # Output format
```

### Command Examples

```bash
# Quick check all instances
sega nginx check

# Detailed SSL check for Instance 1
sega nginx check -i 1 --ssl --detailed

# Check certbot configuration on all instances
sega nginx check --certbot

# JSON output for automation/monitoring
sega nginx check --json

# Comprehensive check (all features)
sega nginx check --ssl --certbot --domains --detailed
```

---

## Implementation Plan

### Phase 1: Core Functionality (HIGH Priority)

**File**: `engine/sega/cli/commands/nginx.py`

Add new command after `status_remote()` (line 345):

```python
@nginx.command('check')
@click.option('--instance', '-i', type=click.Choice(['1', '2', '3', 'all']), 
              default='all', help='Instance to check')
@click.option('--ssl', is_flag=True, help='Check SSL certificates')
@click.option('--certbot', is_flag=True, help='Check certbot auto-renewal')
@click.option('--domains', is_flag=True, help='List configured domains')
@click.option('--detailed', is_flag=True, help='Show detailed information')
@click.option('--format', type=click.Choice(['table', 'json', 'markdown']), 
              default='table', help='Output format')
def check(instance, ssl, certbot, domains, detailed, format):
    """Comprehensive nginx and SSL configuration check.
    
    Validates nginx configuration, SSL certificates, certbot auto-renewal,
    and domain mappings across EC2 instances.
    
    Examples:
        sega nginx check                    # Check all instances
        sega nginx check -i 1 --ssl        # Check Instance 1 SSL
        sega nginx check --certbot         # Check certbot on all
        sega nginx check --format json     # JSON output
    """
    pass  # Implementation below
```

### Phase 2: Data Collection Functions

Create helper module: `engine/sega/infrastructure/nginx_checker.py`

```python
"""
SEGA Nginx Infrastructure Checker
Comprehensive nginx and SSL validation for EC2 instances
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import subprocess
from datetime import datetime

@dataclass
class SSLCertificate:
    """SSL certificate information."""
    name: str
    domains: List[str]
    expiry_date: datetime
    days_remaining: int
    status: str  # VALID, EXPIRING_SOON, EXPIRED

@dataclass
class NginxStatus:
    """Nginx service status."""
    service_active: bool
    config_valid: bool
    uptime: str
    last_reload: str

@dataclass
class CertbotStatus:
    """Certbot auto-renewal status."""
    installed: bool
    timer_active: bool
    next_renewal: Optional[datetime]

@dataclass
class InstanceCheckResult:
    """Complete check result for an instance."""
    instance_num: str
    instance_ip: str
    nginx: NginxStatus
    ssl_certs: List[SSLCertificate]
    certbot: CertbotStatus
    domains: List[str]
    issues: List[str]  # List of detected issues

class NginxChecker:
    """Nginx infrastructure checker."""
    
    def __init__(self, ssh_key_path, ssh_options):
        self.ssh_key = ssh_key_path
        self.ssh_opts = ssh_options
    
    def check_instance(self, instance, check_ssl=True, check_certbot=True,
                      check_domains=True) -> InstanceCheckResult:
        """Run comprehensive check on an instance."""
        pass
    
    def _check_nginx_status(self, instance) -> NginxStatus:
        """Check nginx service status."""
        cmd = ["ssh", "-i", str(self.ssh_key), *self.ssh_opts, instance.ssh_host,
               "sudo nginx -t 2>&1 && systemctl status nginx --no-pager"]
        # Parse output
        pass
    
    def _check_ssl_certificates(self, instance) -> List[SSLCertificate]:
        """Check SSL certificates via certbot."""
        cmd = ["ssh", "-i", str(self.ssh_key), *self.ssh_opts, instance.ssh_host,
               "sudo certbot certificates 2>/dev/null"]
        # Parse certbot output
        pass
    
    def _check_certbot_timer(self, instance) -> CertbotStatus:
        """Check certbot auto-renewal configuration."""
        cmd = ["ssh", "-i", str(self.ssh_key), *self.ssh_opts, instance.ssh_host,
               "which certbot && sudo systemctl status certbot.timer --no-pager 2>&1"]
        # Parse output
        pass
    
    def _check_domains(self, instance) -> List[str]:
        """Extract configured domains from nginx config."""
        cmd = ["ssh", "-i", str(self.ssh_key), *self.ssh_opts, instance.ssh_host,
               "sudo grep 'server_name' /etc/nginx/sites-enabled/default.conf"]
        # Parse server_name lines
        pass
    
    def format_results(self, results: List[InstanceCheckResult], 
                      format: str) -> str:
        """Format results as table, json, or markdown."""
        if format == 'json':
            return self._format_json(results)
        elif format == 'markdown':
            return self._format_markdown(results)
        else:
            return self._format_table(results)
```

### Phase 3: Output Formatting

**Table Format** (default):
```
================================================================================
Instance 1 (203.0.113.10) - Group 1 Projects
================================================================================
Nginx Service:   ✅ Active (1d 4h uptime)
Config Valid:    ✅ OK
Last Reload:     2026-01-04 05:55:00 UTC

SSL Certificates: 9 certificates
  ✅ app.example.com             Expires: Apr 1, 2026 (85 days)
  ✅ www.example.com             Expires: Apr 1, 2026 (85 days)
  ✅ api.example.com             Expires: Apr 1, 2026 (85 days)
  ... (6 more)

Certbot Auto-Renewal:  ✅ Active
  Next Check: Mon 2026-01-05 13:25:45 UTC

Domains Configured: 11 domains
  • app.example.com, api.example.com
  • cli.example.dev, scanner.example.com, badge.example.com
  ... (6 more)

Issues: None
```

**JSON Format**:
```json
{
  "instances": [
    {
      "instance_num": "1",
      "instance_ip": "203.0.113.10",
      "nginx": {
        "service_active": true,
        "config_valid": true,
        "uptime": "1d 4h",
        "last_reload": "2026-01-04T05:55:00Z"
      },
      "ssl_certificates": [
        {
          "name": "app.example.com",
          "domains": ["app.example.com", "beta.example.com", "www.example.com"],
          "expiry_date": "2026-04-01T00:04:21Z",
          "days_remaining": 85,
          "status": "VALID"
        }
      ],
      "certbot": {
        "installed": true,
        "timer_active": true,
        "next_renewal": "2026-01-05T13:25:45Z"
      },
      "domains": ["app.example.com", "api.example.com", ...],
      "issues": []
    }
  ]
}
```

### Phase 4: Issue Detection & Reporting

**Detected Issues**:

```python
def detect_issues(self, result: InstanceCheckResult) -> List[str]:
    """Detect common nginx/SSL issues."""
    issues = []
    
    # Check 1: Nginx service down
    if not result.nginx.service_active:
        issues.append("❌ CRITICAL: Nginx service not running")
    
    # Check 2: Invalid nginx config
    if not result.nginx.config_valid:
        issues.append("❌ CRITICAL: Nginx configuration invalid")
    
    # Check 3: No SSL certificates
    if not result.ssl_certs:
        issues.append("⚠️  WARNING: No SSL certificates found (HTTP-only deployment)")
    
    # Check 4: Expiring certificates (< 30 days)
    for cert in result.ssl_certs:
        if cert.days_remaining < 30:
            issues.append(f"⚠️  WARNING: {cert.name} expires in {cert.days_remaining} days")
    
    # Check 5: Certbot not installed/configured
    if result.ssl_certs and not result.certbot.installed:
        issues.append("⚠️  WARNING: SSL certificates present but certbot not installed")
    
    if result.certbot.installed and not result.certbot.timer_active:
        issues.append("⚠️  WARNING: Certbot installed but auto-renewal disabled")
    
    # Check 6: Missing listen 443 blocks (if we can detect this)
    # Would require parsing nginx config - Phase 2 enhancement
    
    return issues
```

**Issue Summary**:
```
================================================================================
Summary: 3 instances checked
================================================================================
✅ Instance 1: Healthy (9 SSL certs, auto-renewal active)
✅ Instance 2: Healthy (13 SSL certs, auto-renewal active)
⚠️  Instance 3: 3 issues detected

Instance 3 Issues:
  ⚠️  WARNING: No SSL certificates found (HTTP-only deployment)
  ⚠️  WARNING: Certbot not installed
  ⚠️  WARNING: Certbot auto-renewal not configured

Recommendation: Run 'sega nginx setup-ssl --instance 3' to install certificates
```

---

## Integration Points

### 1. Existing Infrastructure

**Leverage**:
- `ec2_config.py`: Instance definitions (INSTANCE1, INSTANCE2, INSTANCE3)
- `get_ssh_key_path()`, `get_ssh_options()`: SSH configuration
- `build_ssh_command()`: SSH command construction

**Import**:
```python
from ...infrastructure import (
    INSTANCE1, INSTANCE2, INSTANCE3,
    get_ssh_key_path, get_ssh_options,
)
```

### 2. Doctor Command Integration (Optional)

Add alias for infrastructure health checking:

```python
# In doctor.py
@doctor.command('infrastructure')
@click.option('--nginx', is_flag=True, help='Check nginx configuration')
@click.option('--ssl', is_flag=True, help='Check SSL certificates')
def infrastructure(nginx, ssl):
    """Check EC2 infrastructure health.
    
    Alias for: sega nginx check --ssl --certbot
    """
    from .nginx import check as nginx_check
    ctx = click.get_current_context()
    ctx.invoke(nginx_check, instance='all', ssl=True, certbot=True)
```

### 3. Monitoring Integration (Future)

**the metrics service Integration** (when implemented):
- Send check results to the metrics service metrics endpoint
- Track SSL expiry metrics over time
- Alert on configuration issues

**Example**:
```python
if telemetry_enabled:
    send_metrics({
        'instance': instance_num,
        'nginx_status': 'active' if nginx.service_active else 'inactive',
        'ssl_cert_count': len(ssl_certs),
        'min_days_to_expiry': min(cert.days_remaining for cert in ssl_certs),
        'issues_count': len(issues)
    })
```

---

## Testing Strategy

### Unit Tests

**File**: `tests/cli/commands/test_nginx_check.py`

```python
def test_nginx_check_instance_1():
    """Test checking Instance 1."""
    runner = CliRunner()
    result = runner.invoke(nginx_check, ['--instance', '1', '--ssl'])
    assert result.exit_code == 0
    assert "Instance 1" in result.output
    assert "SSL Certificates" in result.output

def test_nginx_check_all_instances():
    """Test checking all instances."""
    runner = CliRunner()
    result = runner.invoke(nginx_check, ['--format', 'json'])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert 'instances' in data

def test_nginx_check_detects_missing_certbot():
    """Test issue detection for missing certbot."""
    # Mock SSH response with no certbot
    result = checker.check_instance(mock_instance, check_certbot=True)
    assert any("certbot not installed" in issue for issue in result.issues)
```

### Integration Tests

**Manual Testing Checklist**:
- [ ] Check Instance 1 (has SSL)
- [ ] Check Instance 2 (has SSL)
- [ ] Check Instance 3 (no SSL)
- [ ] JSON output format
- [ ] Markdown output format
- [ ] Issue detection accuracy
- [ ] SSH connection handling
- [ ] Error handling (unreachable instance)

---

## Documentation Updates

### 1. CLI Reference

**File**: `docs/reference/cli-reference.md`

Add section:
```markdown
### sega nginx check

Comprehensive nginx and SSL configuration validation for EC2 instances.

**Usage**:
```bash
sega nginx check [OPTIONS]
```

**Options**:
- `--instance, -i <1|2|3|all>`: Instance to check (default: all)
- `--ssl`: Check SSL certificates
- `--certbot`: Check certbot auto-renewal
- `--domains`: List configured domains
- `--detailed`: Show detailed certificate information
- `--format <table|json|markdown>`: Output format

**Examples**:
```bash
# Check all instances
sega nginx check

# Check Instance 1 SSL in detail
sega nginx check -i 1 --ssl --detailed

# Get JSON output for automation
sega nginx check --format json
```
```

### 2. Feature Map

**File**: `docs/reference/FEATURE_MAP.md`

Update nginx section:
```markdown
## 8. NGINX Configuration Management

**Commands**: `sega nginx [setup|ssl|status|reload|deploy|check]`

| Feature | Location | Status |
|---------|----------|--------|
| ... (existing) | ... | ... |
| **Remote Infrastructure Checking** | `engine/sega/cli/commands/nginx.py:check()` | ✅ IMPLEMENTED |
| **SSL Certificate Validation** | `engine/sega/infrastructure/nginx_checker.py` | ✅ IMPLEMENTED |
| **Certbot Auto-Renewal Check** | `engine/sega/infrastructure/nginx_checker.py` | ✅ IMPLEMENTED |
| **Issue Detection & Reporting** | `engine/sega/infrastructure/nginx_checker.py:detect_issues()` | ✅ IMPLEMENTED |
```

### 3. NGINX Deployment Procedure

**File**: `docs/guides/procedures/NGINX_DEPLOYMENT_PROCEDURE.md`

Add section at end:
```markdown
## Automated Validation

After deployment, verify configuration with SEGA:

```bash
# Check nginx configuration and SSL
sega nginx check --instance 1 --ssl --certbot --detailed

# Expected output:
# ✅ Nginx service active
# ✅ Configuration valid
# ✅ SSL certificates present
# ✅ Certbot auto-renewal active
```

For automation/monitoring, use JSON output:

```bash
sega nginx check --format json > nginx-status.json
```
```

---

## Implementation Timeline

### Sprint 1 (Week 1): Core Implementation
- [ ] Create `nginx_checker.py` module
- [ ] Implement `NginxChecker` class with data collection
- [ ] Add `sega nginx check` command skeleton
- [ ] Implement SSH commands for nginx/SSL data collection
- [ ] Basic table output format

### Sprint 2 (Week 2): Features & Formatting
- [ ] Add JSON output format
- [ ] Add Markdown output format
- [ ] Implement issue detection logic
- [ ] Add detailed mode for certificate info
- [ ] Add domain listing feature

### Sprint 3 (Week 3): Polish & Documentation
- [ ] Write unit tests
- [ ] Integration testing on all 3 instances
- [ ] Update CLI reference documentation
- [ ] Update Feature Map
- [ ] Update NGINX deployment procedure
- [ ] Code review and refinement

### Sprint 4 (Week 4): Future Enhancements
- [ ] the metrics service metrics integration
- [ ] `sega doctor infrastructure` alias
- [ ] Auto-fix suggestions for detected issues
- [ ] Certificate renewal automation

---

## Success Criteria

### Must Have (MVP)
- ✅ Check nginx service status on remote instances
- ✅ List SSL certificates with expiry dates
- ✅ Check certbot auto-renewal timer status
- ✅ Detect and report common issues
- ✅ Support all 3 EC2 instances
- ✅ Table and JSON output formats

### Should Have
- ✅ Detailed certificate information
- ✅ Domain listing from nginx configs
- ✅ Markdown output for documentation
- ✅ Issue severity levels (CRITICAL, WARNING, INFO)

### Could Have
- ⏳ the metrics service metrics integration
- ⏳ Auto-fix recommendations
- ⏳ Historical tracking of certificate expiry
- ⏳ Slack/email alerts for expiring certificates

---

## Security Considerations

1. **SSH Key Security**:
   - Use existing `get_ssh_key_path()` (checks permissions)
   - Never log SSH key paths or contents
   - Use `BatchMode=yes` to prevent interactive prompts

2. **Sensitive Data**:
   - Don't log certificate private keys
   - Sanitize error messages (no credential leaking)
   - JSON output suitable for logs (no secrets)

3. **Privilege Requirements**:
   - Requires `sudo` access on EC2 instances (certbot, nginx configs)
   - Document in README that command requires SSH key with sudo access

---

## Alternatives Considered

### Alternative 1: Create New `sega infrastructure` Command Group
❌ Rejected because:
- Creates fragmentation (nginx management split)
- Less discoverable than extending existing `sega nginx`
- Would need to duplicate EC2 instance selection logic

### Alternative 2: Integrate into `sega doctor`
❌ Rejected because:
- Doctor focuses on local environment checks
- Nginx operations already under `sega nginx`
- Could add as alias (`sega doctor infrastructure` → `sega nginx check`)

### Alternative 3: Create Standalone `sega check-nginx` Command
❌ Rejected because:
- Violates SEGA grouping conventions
- Less intuitive than `sega nginx check`
- Harder to discover alongside other nginx commands

---

## Recommendation

**Implement as**: `sega nginx check` command

**Rationale**:
1. ✅ Natural extension of existing `sega nginx` command group
2. ✅ Follows SEGA architectural patterns (ec2_config, SSH helpers)
3. ✅ Addresses immediate operational need (SSL verification)
4. ✅ Minimal code duplication (reuses infrastructure)
5. ✅ Extensible for future enhancements (the metrics service integration)

**Next Steps**:
1. Review and approve this plan
2. Begin Sprint 1 implementation
3. Test against all 3 EC2 instances
4. Document and deploy

---

**File Reference**: `~/sega/docs/plans/NGINX_CHECK_INTEGRATION_PLAN.md`
**Related**: 
- [NGINX Configuration Standards](/docs/standards/deployment/NGINX_CONFIGURATION_STANDARDS.md)
- [NGINX Deployment Procedure](/docs/guides/procedures/NGINX_DEPLOYMENT_PROCEDURE.md)
- [Feature Map](~/sega/docs/reference/FEATURE_MAP.md)
