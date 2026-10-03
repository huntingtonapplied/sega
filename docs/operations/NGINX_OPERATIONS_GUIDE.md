# SEGA Nginx Operations Guide

**Version**: 1.0.0
**Status**: ACTIVE - SEGA OPERATIONAL REFERENCE
**Last Updated**: 2026-01-05
**Maintained By**: SEGA Division

---

## 📋 Document Navigation

**THIS IS THE OPERATIONAL GUIDE for using SEGA commands to manage nginx across your infrastructure.**

### Quick Links
| Document | Purpose | Location |
|----------|---------|----------|
| **THIS DOCUMENT** | SEGA nginx commands & automation | `/sega/docs/operations/` |
| **[NGINX_CONFIGURATION_STANDARDS.md](/docs/standards/deployment/NGINX_CONFIGURATION_STANDARDS.md)** | Config templates & standards | `/docs/standards/deployment/` |
| **[NGINX_SSL_LESSONS_LEARNED.md](/docs/standards/deployment/NGINX_SSL_LESSONS_LEARNED.md)** | Historical issues & solutions | `/docs/standards/deployment/` |
| **[NGINX_DEPLOYMENT_PROCEDURE.md](/docs/guides/procedures/NGINX_DEPLOYMENT_PROCEDURE.md)** | Manual deployment steps | `/docs/guides/procedures/` |

---

## Purpose

This guide covers **SEGA-based automation** for nginx infrastructure management across all 3 EC2 instances:
- Instance 1 (203.0.113.10): 11 projects
- Instance 2 (203.0.113.11): 4 projects  
- Instance 3 (203.0.113.12): 5 projects

Total: 26+ SSL certificates, 20+ production domains

---

## 🔒 SSL STANDARD

**SSL on origin is the standard. This is non-negotiable.**

All SEGA nginx operations enforce:
- ✅ Port 443 with SSL certificates required
- ✅ Cloudflare "Full (Strict)" mode required
- ❌ Cloudflare "Flexible" mode is a policy violation
- ❌ HTTP-only production configs are rejected

If `sega nginx check` detects missing SSL blocks on production instances, this is a **CRITICAL** issue requiring immediate remediation.

---

## Quick Start

### Check Infrastructure Health
```bash
# Check all instances (comprehensive)
sega nginx check

# Check specific instance with SSL details
sega nginx check -i 1 --ssl --detailed

# Full check with all options
sega nginx check --ssl --certbot --domains --detailed

# Generate markdown report
sega nginx check --format markdown > nginx-status-$(date +%Y%m%d).md

# JSON output for automation
sega nginx check --format json | jq .
```

### Common Operations
```bash
# Quick health check before deployment
sega nginx check -i 2 --ssl

# Monitor certificate expiry
sega nginx check --ssl | grep -i "expiring\|expired"

# List all configured domains
sega nginx check --domains

# Verify certbot auto-renewal
sega nginx check --certbot
```

---

## Command Reference: `sega nginx check`

### Synopsis
```bash
sega nginx check [OPTIONS]
```

### Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `-i, --instance` | 1, 2, 3, all | all | Instance to check |
| `--ssl` | - | - | Check SSL certificates |
| `--certbot` | - | - | Check certbot auto-renewal |
| `--domains` | - | - | List configured domains |
| `--detailed` | - | - | Show detailed information |
| `--format` | table, json, markdown | table | Output format |

### Examples

#### Example 1: Quick Health Check
```bash
$ sega nginx check

Instance 1 (203.0.113.10):
  Status: ✅ Active (1d 16h uptime)
  Config: ✅ Valid
  Issues: None

Instance 2 (203.0.113.11):
  Status: ✅ Active (5d uptime)
  Config: ✅ Valid
  Issues: None

Instance 3 (203.0.113.12):
  Status: ✅ Active (1d 2h uptime)
  Config: ✅ Valid
  Issues: None
```

#### Example 2: SSL Certificate Monitoring
```bash
$ sega nginx check -i 1 --ssl --detailed

Instance 1 - prod-01 (203.0.113.10)
Nginx: ✅ Active

SSL Certificates (9):
┌─────────────────────────┬────────────────────────────┬──────────┬────────┐
│ Certificate             │ Domains                    │ Expiry   │ Status │
├─────────────────────────┼────────────────────────────┼──────────┼────────┤
│ service-a.example.com          │ service-a.example.com,            │ 85 days  │ ✅     │
│                         │ app.service-a.example.com,        │          │        │
│                         │ www.service-a.example.com         │          │        │
├─────────────────────────┼────────────────────────────┼──────────┼────────┤
│ service-b.example.com           │ service-b.example.com,             │ 85 days  │ ✅     │
│                         │ app.service-b.example.com,         │          │        │
│                         │ www.service-b.example.com          │          │        │
└─────────────────────────┴────────────────────────────┴──────────┴────────┘
```

#### Example 3: Pre-Deployment Validation
```bash
$ sega nginx check -i 2 --ssl --certbot
Instance 2 (203.0.113.11):
  Nginx: ✅ Active
  SSL: ✅ 12 certificates valid
  Certbot: ✅ Auto-renewal active (next: 16h)
  Result: READY FOR DEPLOYMENT
```

#### Example 4: Automated Monitoring (JSON)
```bash
$ sega nginx check --format json | jq '.instances[] | select(.issues != [])'
# Returns only instances with issues
```

#### Example 5: Documentation Report
```bash
$ sega nginx check --format markdown > nginx-infrastructure-report.md
# Generates markdown table suitable for documentation
```

---

## Issue Detection & Recommendations

### Critical Issues (🔴 Deployment Blockers)

| Issue | Detection | Recommendation |
|-------|-----------|----------------|
| **Nginx not running** | Service inactive | `sudo systemctl start nginx` |
| **Invalid config** | `nginx -t` fails | Review syntax, check cert paths |
| **Expired certificates** | Expiry date < today | `sudo certbot renew --force-renewal` |
| **Missing SSL (502 errors)** | No `listen 443` blocks | See [NGINX_SSL_LESSONS_LEARNED.md](/docs/standards/deployment/NGINX_SSL_LESSONS_LEARNED.md) |

### Warnings (⚠️ Action Required Soon)

| Issue | Detection | Recommendation |
|-------|-----------|----------------|
| **Certificates expiring soon** | Expiry < 30 days | `sudo certbot renew` (or wait for auto-renewal) |
| **Certbot not installed** | Command not found | `sudo apt install certbot python3-certbot-nginx -y` |
| **Auto-renewal disabled** | Timer inactive | `sudo systemctl enable --now certbot.timer` |
| **HTTP-only config** | 0 SSL certificates | Install SSL per deployment procedure |

### How SEGA Detects Issues

**Nginx Service Status**:
```bash
# Command: sudo systemctl status nginx
# Checks: active/inactive, uptime, last reload
```

**Configuration Validity**:
```bash
# Command: sudo nginx -t
# Checks: syntax errors, missing cert files, port conflicts
```

**SSL Certificates**:
```bash
# Command: sudo certbot certificates
# Extracts: domain names, expiry dates, certificate paths
# Status: VALID (>30d), EXPIRING_SOON (<30d), EXPIRED (<0d)
```

**Certbot Auto-Renewal**:
```bash
# Command: sudo systemctl status certbot.timer
# Checks: timer active, next scheduled run
```

**Configured Domains**:
```bash
# Command: sudo grep -r "server_name" /etc/nginx/sites-enabled/
# Extracts: all server_name directives
```

---

## Deployment Workflows

### Workflow 1: New Project Deployment

**Pre-Deployment**:
```bash
# 1. Check instance health
sega nginx check -i [N]

# 2. Verify port availability (see PORT_ALLOCATION_STANDARDS.md)
ssh -i ~/prod-key.pem ubuntu@[INSTANCE_IP] \
  "sudo netstat -tlnp | grep :[PORT]"
```

**Deployment**:
```bash
# 3. Deploy nginx config (manual or via SEGA)
# See NGINX_DEPLOYMENT_PROCEDURE.md for steps

# 4. Run certbot
ssh -i ~/prod-key.pem ubuntu@[INSTANCE_IP] \
  "sudo certbot --nginx -d domain.com -d www.domain.com -d app.domain.com \
   --non-interactive --agree-tos --email admin@domain.com"
```

**Post-Deployment**:
```bash
# 5. Validate
sega nginx check -i [N] --ssl --detailed

# 6. Test endpoints
curl -I https://domain.com
curl -I https://app.domain.com

# 7. Enable Cloudflare proxy (if using)
# Cloudflare Dashboard → DNS → Change to "Proxied" (orange cloud)
```

### Workflow 2: SSL Certificate Renewal

**Automatic** (via certbot.timer):
```bash
# Runs daily, renews certs < 30 days from expiry
# No manual intervention required

# Verify timer active:
sega nginx check --certbot
```

**Manual** (if needed):
```bash
# Test renewal (dry run)
ssh -i ~/prod-key.pem ubuntu@[INSTANCE_IP] \
  "sudo certbot renew --dry-run"

# Force renewal
ssh -i ~/prod-key.pem ubuntu@[INSTANCE_IP] \
  "sudo certbot renew --force-renewal"

# Verify
sega nginx check -i [N] --ssl
```

### Workflow 3: Adding Product App Subdomain

**Scenario**: Project has landing app (domain.com), adding product app (app.domain.com)

```bash
# 1. Configure DNS in Cloudflare
# Type: A
# Name: app
# Content: [instance IP]

# 2. Expand existing certificate
ssh -i ~/prod-key.pem ubuntu@[INSTANCE_IP] \
  "sudo certbot certonly --nginx --expand \
   -d domain.com -d www.domain.com -d app.domain.com \
   --non-interactive"

# 3. Update nginx config (add app.* server block)
# See NGINX_CONFIGURATION_STANDARDS.md for template

# 4. Reload nginx
ssh -i ~/prod-key.pem ubuntu@[INSTANCE_IP] \
  "sudo nginx -t && sudo systemctl reload nginx"

# 5. Verify
sega nginx check -i [N] --ssl
curl -I https://app.domain.com
```

### Workflow 4: Troubleshooting 502 Errors

**Symptom**: HTTPS returns 502 Bad Gateway, HTTP works

```bash
# 1. Diagnose
sega nginx check -i [N] --ssl

# 2. Check for SSL blocks
ssh -i ~/prod-key.pem ubuntu@[INSTANCE_IP] \
  "sudo grep -r 'listen 443' /etc/nginx/sites-enabled/"

# If empty → No SSL configured

# 3. Install SSL
ssh -i ~/prod-key.pem ubuntu@[INSTANCE_IP] \
  "sudo certbot --nginx -d domain.com -d www.domain.com \
   --non-interactive --agree-tos --email admin@domain.com"

# 4. Verify fix
curl -I https://domain.com  # Should return 200 or 301, not 502
sega nginx check -i [N] --ssl
```

**See full troubleshooting**: [NGINX_SSL_LESSONS_LEARNED.md](/docs/standards/deployment/NGINX_SSL_LESSONS_LEARNED.md#critical-lesson-cloudflare-502-error-pattern)

---

## Infrastructure Status (Current)

### Summary (as of 2026-01-05)
```
Total Instances: 3
Total SSL Certificates: 26
Certbot Auto-Renewal: ✅ Active on all instances
Nginx Service: ✅ Active on all instances
Configuration: ✅ Valid on all instances
```

### Instance 1 - prod-01 (203.0.113.10)
```
Projects: 11 (Group 1 + Group 4 temp)
SSL Certificates: 9
  - service-a.example.com (85 days)
  - service-b.example.com (85 days)
  - service-c.example.com (85 days)
  - example.com (83 days)
  - service-d.example.com (85 days)
  - service-e.example.com (85 days)
  - service-f.example.com (85 days)
  - service-g.example.com (85 days)
  - service-h.example.com (85 days)
Certbot: ✅ Active (next: 16h)
Status: ✅ Healthy
```

### Instance 2 - prod-02 (203.0.113.11)
```
Projects: 4 (Group 2)
SSL Certificates: 12
  - apps.example.dev (85 days)
  - lab.example.com (76 days)
  - service-i.example.com (85 days)
  - service-j.example.com (85 days)
  - service-k.example.com (85 days)
  - service-l.example.com (85 days)
  - service-m.example.com (85 days)
  - example.com (76 days)
  - service-n.example.com (85 days)
  - cli.example.dev (85 days)
  - service-o.example.com (85 days)
  - scanner.example.com (85 days)
Certbot: ✅ Active (next: 46min)
Status: ✅ Healthy
```

### Instance 3 - prod-03 (203.0.113.12)
```
Projects: 5 (Group 3)
SSL Certificates: 5
  - apps.example.dev (89 days)
  - service-l.example.com (89 days)
  - service-m.example.com (89 days)
  - service-n.example.com (89 days)
  - service-o.example.com (89 days)
Certbot: ✅ Active (next: 7h)
Status: ✅ Healthy
```

---

## Monitoring & Alerting

### Daily Health Check (Recommended)
```bash
#!/bin/bash
# Save as: ~/scripts/daily-nginx-check.sh

# Run comprehensive check
sega nginx check --ssl --certbot --format markdown > \
  ~/reports/nginx-$(date +%Y%m%d).md

# Check for issues
ISSUES=$(sega nginx check --format json | jq -r '.instances[].issues | length' | awk '{s+=$1} END {print s}')

if [ "$ISSUES" -gt 0 ]; then
  echo "⚠️  Nginx issues detected: $ISSUES"
  sega nginx check --detailed
  # Optional: Send alert via Slack/email
else
  echo "✅ All nginx instances healthy"
fi
```

### Pre-Deployment Check (Required)
```bash
#!/bin/bash
# Run before any deployment

INSTANCE=$1
if [ -z "$INSTANCE" ]; then
  echo "Usage: $0 [instance_number]"
  exit 1
fi

echo "🔍 Checking Instance $INSTANCE..."
sega nginx check -i $INSTANCE --ssl --certbot --detailed

# Exit code: 0 = healthy, 1 = issues
```

### Certificate Expiry Monitoring
```bash
# Check for certificates expiring in < 30 days
sega nginx check --ssl --format json | \
  jq -r '.instances[].ssl_certificates[] | 
         select(.days_remaining < 30) | 
         "\(.certificate_name): \(.days_remaining) days"'
```

### Integration with a metrics service (Future)
```
Planned features:
- Real-time certificate expiry alerts
- Nginx service uptime tracking
- Historical metrics (reload frequency, errors)
- Dashboard integration
```

---

## Configuration Management

### SEGA Config Storage

**Location**: `~/sega/config/`

```
sega/config/
├── unified-instance1.conf  # Instance 1 config
├── unified-instance2.conf  # Instance 2 config
├── unified-instance3.conf  # Instance 3 config
└── archive/
    ├── unified.conf        # Historical single-instance
    └── [dated backups]
```

### Config Deployment Pattern

**Instance-specific configs** (required for multi-instance):
```bash
# Deploy to Instance 1
scp -i ~/prod-key.pem \
  ~/sega/config/unified-instance1.conf \
  ubuntu@203.0.113.10:/tmp/site.conf

ssh -i ~/prod-key.pem ubuntu@203.0.113.10 \
  "sudo cp /tmp/site.conf /etc/nginx/sites-available/site.conf && \
   sudo ln -sf /etc/nginx/sites-available/site.conf /etc/nginx/sites-enabled/ && \
   sudo nginx -t && sudo systemctl reload nginx"

# Verify
sega nginx check -i 1
```

**Why instance-specific configs?**
- Each instance has different SSL certificates
- Unified config references certs that don't exist on all instances
- Nginx fails to start if cert paths are invalid

See: [NGINX_SSL_LESSONS_LEARNED.md - Instance-Specific Configs](/docs/standards/deployment/NGINX_SSL_LESSONS_LEARNED.md#critical-lesson-instance-specific-configs-required)

---

## Automation Roadmap

### Phase 1 ✅ (Complete)
- [x] `sega nginx check` command
- [x] Multi-instance support
- [x] SSL certificate monitoring
- [x] Certbot auto-renewal verification
- [x] Multi-format output (table, JSON, markdown)

### Phase 2 🚧 (In Progress)
- [ ] `sega nginx deploy` - Automated config deployment
- [ ] `sega nginx cert renew` - Force certificate renewal
- [ ] `sega nginx cert expand` - Add domains to existing certs
- [ ] Config validation before deployment

### Phase 3 📋 (Planned)
- [ ] `sega nginx doctor` - Auto-fix common issues
- [ ] the metrics service metrics integration
- [ ] Alert notifications (Slack/email)
- [ ] Historical certificate tracking
- [ ] Automated backup of configs

### Phase 4 🔮 (Future)
- [ ] `sega nginx rollback` - Revert to previous config
- [ ] A/B testing support for nginx configs
- [ ] Performance metrics (request latency, cache hit rates)
- [ ] Automated security hardening

---

## Troubleshooting Guide

### Issue: "sega command not found"
```bash
# Solution: Ensure SEGA is installed and in PATH
cd ~/sega
pip install -e .

# Or use full path
python -m sega.cli nginx check
```

### Issue: SSH connection fails
```bash
# Check SSH key permissions
ls -la ~/prod-key.pem  # Should be 400 or 600
chmod 400 ~/prod-key.pem

# Test connection
ssh -i ~/prod-key.pem ubuntu@203.0.113.10 "echo OK"
```

### Issue: "Permission denied" on nginx commands
```bash
# SEGA runs nginx commands via sudo over SSH
# Ensure ubuntu user has sudo privileges (default on EC2)

# Test sudo access
ssh -i ~/prod-key.pem ubuntu@203.0.113.10 "sudo nginx -t"
```

### Issue: JSON output malformed
```bash
# Possible causes:
# 1. SSH warnings mixed with JSON
# 2. Parsing errors in nginx output

# Use --detailed flag for verbose output
sega nginx check --format json --detailed > output.json

# Validate JSON
jq . output.json
```

### Issue: Certificate not detected
```bash
# Possible causes:
# 1. Certbot not installed
# 2. Certificates exist but not via certbot (manual install)

# Verify certbot
ssh -i ~/prod-key.pem ubuntu@[IP] "which certbot"

# Check for certs manually
ssh -i ~/prod-key.pem ubuntu@[IP] \
  "sudo ls -la /etc/letsencrypt/live/"
```

---

## Best Practices

### Before Any Deployment
1. ✅ Run `sega nginx check -i [N]` to verify instance health
2. ✅ Review [NGINX_DEPLOYMENT_PROCEDURE.md](/docs/guides/procedures/NGINX_DEPLOYMENT_PROCEDURE.md)
3. ✅ Verify port availability in [PORT_ALLOCATION_STANDARDS.md](/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md)
4. ✅ Check DNS configured in Cloudflare
5. ✅ Have rollback plan ready

### After Deployment
1. ✅ Run `sega nginx check -i [N] --ssl --detailed`
2. ✅ Test all endpoints (HTTP, HTTPS, WebSocket)
3. ✅ Verify Cloudflare proxy settings
4. ✅ Monitor logs for errors: `sudo tail -f /var/log/nginx/error.log`
5. ✅ Document any deviations or issues

### Regular Maintenance
- **Daily**: Automated health check script
- **Weekly**: Review `sega nginx check` output for warnings
- **Monthly**: Certificate expiry review, config audit
- **Quarterly**: Documentation review, lessons learned update

### Security Checklist
- [ ] Certbot auto-renewal active on all instances
- [ ] Cloudflare SSL mode: "Full (Strict)"
- [ ] Security headers configured (X-Frame-Options, X-Content-Type-Options, etc.)
- [ ] HSTS enabled on production domains
- [ ] Rate limiting configured (if needed)
- [ ] Access logs monitored for suspicious activity

---

## Related Documentation

### Primary References (Read in Order)
1. **[NGINX_SSL_LESSONS_LEARNED.md](/docs/standards/deployment/NGINX_SSL_LESSONS_LEARNED.md)** - WHY we do it this way
2. **[NGINX_CONFIGURATION_STANDARDS.md](/docs/standards/deployment/NGINX_CONFIGURATION_STANDARDS.md)** - WHAT the standards are
3. **[NGINX_DEPLOYMENT_PROCEDURE.md](/docs/guides/procedures/NGINX_DEPLOYMENT_PROCEDURE.md)** - HOW to deploy
4. **THIS DOCUMENT** - SEGA automation tools

### Implementation Details
- **[NGINX_CHECK_IMPLEMENTATION_2026_01_05.md](../reports/NGINX_CHECK_IMPLEMENTATION_2026_01_05.md)** - Implementation report
- **[NGINX_CHECK_INTEGRATION_PLAN.md](../plans/NGINX_CHECK_INTEGRATION_PLAN.md)** - Design documentation
- **[FEATURE_MAP.md](../reference/FEATURE_MAP.md)** - SEGA feature overview

### Infrastructure
- **[EC2_INSTANCE_REGISTRY.md](/docs/operations/infrastructure/EC2_INSTANCE_REGISTRY.md)** - Instance details
- **[PORT_ALLOCATION_STANDARDS.md](/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md)** - Port assignments
- **[DOMAIN_REGISTRY.md](/docs/architecture/infrastructure/dns/DOMAIN_REGISTRY.md)** - Domain registry

---

## Support & Feedback

### Questions
Submit to: your project tracker

Follow: [Question Submission Standard](/docs/standards/documentation/QUESTION_SUBMISSION_STANDARD.md)

### Issues
Report nginx/SSL issues to:
- Project-level: `/[project]/docs/ISSUES_TRACKER.md`
- Cross-project: `/docs/healer/workers/eagle/CROSS_PROJECT_ERROR_ANALYSIS.md`

### Documentation Updates
This document is maintained by SEGA division. For corrections or additions:
1. Create issue in `/sega/docs/issues/`
2. Submit PR with changes
3. Tag @secretary-division for review

---

**File Reference**: `~/sega/docs/operations/NGINX_OPERATIONS_GUIDE.md`
**Maintained By**: SEGA Division
**Version**: 1.0.0
**Last Updated**: 2026-01-05
**Review Schedule**: Quarterly (next: 2026-04-05)
