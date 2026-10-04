# Domain Testing Quick Reference

**Last Updated**: 2026-01-05

## 🎯 Quick Commands

### Test Everything
```bash
# Test all instances (localhost via SSH) + all production domains
sega probe domain --test-localhost
```

### Test Specific Instance
```bash
# Instance 1 localhost only
sega probe instance --instance 1

# Instance 1 comprehensive (localhost + production)
sega probe domain --instance 1 --test-localhost
```

### Test Specific Projects
```bash
# Service-a localhost + production
sega probe domain -p service-a --test-localhost

# Multiple projects
sega probe domain -p service-a -p service-b -p service-c --test-localhost
```

## 📊 What Gets Tested

| Command | Localhost (SSH) | Production Domains | SSL Check |
|---------|----------------|-------------------|-----------|
| `sega probe instance` | ✅ | ❌ | ❌ |
| `sega probe domain` | ❌ | ✅ | ✅ |
| `sega probe domain --test-localhost` | ✅ | ✅ | ✅ |

## 🔧 Common Options

```bash
--instance 1           # Filter to Instance 1
--timeout 30           # 30 second timeout
--verbose              # Detailed output
--json-output          # JSON format
--ssh-key ~/key.pem    # Custom SSH key
--no-ssl               # Skip SSL verification
--type api             # Only test APIs
--domain production    # Only test production domains
```

## 📍 Project → Instance Mapping

| Instance | IP | Projects |
|----------|-----|----------|
| **1** | 203.0.113.11 | service-a, service-b, service-c, service-d, service-e, service-f<br>service-g, service-h, service-i, service-j, service-k |
| **2** | 203.0.113.12 | service-l, service-m, service-n, service-o |
| **3** | 203.0.113.13 | service-p, service-q, service-r, service-s, service-t |

## 🚨 Troubleshooting

```bash
# SSH connection test
ssh -i ~/your-key.pem ubuntu@203.0.113.11

# Verbose debugging
sega probe instance --instance 1 --verbose

# Manual curl test (from EC2 instance)
ssh -i ~/your-key.pem ubuntu@203.0.113.11 \
  "curl -s http://localhost:8004/health"
```

## 🎓 Examples

### Daily Health Check
```bash
# Quick check: Are all services running on all instances?
sega probe instance
```

### Post-Deployment Verification
```bash
# After deploying service-a to Instance 1
sega probe domain -p service-a --test-localhost --verbose
```

### Debug Production Issues
```bash
# Test service-a everywhere
sega probe domain -p service-a --test-localhost

# Check SSL certificates
sega probe domain -p service-a --domain production
```

---

**Full Documentation**: `docs/operations/COMPREHENSIVE_DOMAIN_TESTING.md`
