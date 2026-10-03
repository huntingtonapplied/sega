# Console Scan Guide

**Status**: ✅ IMPLEMENTED  
**Version**: 1.0  
**Last Updated**: 2026-01-07

## Overview

SEGA Console Scanner provides **two complementary modes** for monitoring portfolio project health:

1. **Status Dashboard** - Fast HTTP checks (2-3 seconds for all 22 projects)
2. **Console Scanner** - Deep Playwright analysis with error reports (60-90 seconds)

## Quick Start

### Fast Status Check (Dashboard)

```bash
# Quick HTTP check for all projects
sega probe scan --dashboard --all

# Check specific instance
sega probe scan --dashboard --instance 1

# Check internal dev domains
sega probe scan --dashboard --all --domain-type internal

# Compact view
sega probe scan --dashboard --all --compact
```

### Deep Console Analysis (Report)

```bash
# Full scan with detailed report
sega probe scan --all --report

# Scan specific projects
sega probe scan -p service-b -p service-c --report

# Minimal detail
sega probe scan --all --report --detail minimal

# Full detail with stack traces
sega probe scan -p service-a --report --detail full

# JSON export
sega probe scan --all --report --json
```

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────┐
│  Status Dashboard (Fast)                                │
│  ├─ HTTP HEAD/GET requests                             │
│  ├─ No browser overhead                                │
│  └─ 2-3 seconds for all 22 projects                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Console Scanner (Deep)                                 │
│  ├─ Playwright browser automation                      │
│  ├─ Console log capture & deduplication                │
│  ├─ Network failure tracking                           │
│  ├─ Performance metrics                                │
│  └─ Screenshot capture on errors                       │
└─────────────────────────────────────────────────────────┘
```

### Files Created

| File | Purpose |
|------|---------|
| `engine/sega/probe/console_message.py` | Message processing, truncation, deduplication |
| `engine/sega/probe/console_scanner.py` | Playwright-based console scanning |
| `engine/sega/probe/status_dashboard.py` | Lightweight HTTP status checks |
| `engine/sega/probe/scan_reporter.py` | Markdown & JSON report generation |
| `engine/sega/cli/commands/probe.py` | CLI command integration (scan subcommand) |

### Integration with Existing Infrastructure

**Reuses**:
- `DomainTestRunner` - Domain URL building and project registry
- Domain registry (`config/domain_registry.yaml`) - No duplication
- Existing domain patterns (landing, `app.domain`, `api.domain`)

## Usage Examples

### Status Dashboard Examples

#### All Projects Overview

```bash
$ sega probe scan --dashboard --all

┌──────────────────────────────────────────────────────────────────────────────┐
│                        PROBE STATUS DASHBOARD                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PROJECT       LANDING            PRODUCT APP         STATUS                │
│  ──────────────────────────────────────────────────────────────────────────  │
│  service-a      ✓ 200 (0.2s)      ✗ 500               🔴                    │
│  service-b     ✓ 200 (0.1s)      ✓ 200 (0.2s)        🟢                    │
│  service-c          ✓ 200 (0.3s)      ✓ 200 (0.4s)        🟢                    │
│  ...                                                                         │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ HEALTHY: 18/22  │  WARNING: 0  │  CRITICAL: 4  │  [r] Refresh  [q] Quit    │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Compact View

```bash
$ sega probe scan --dashboard --all --compact

✓ 18/22 healthy │ ⚠ 0 warning │ ✗ 4 critical

Critical projects:
  • service-a
  • web-app
  • example-project
  • api-service
```

### Console Scan Examples

#### Full Report Generation

```bash
$ sega probe scan --all --report

🔍 Scanning pages for console errors...

  ✓ service-a       (2.3s) - 12 errors
  ✓ service-b      (1.8s) - clean
  ✓ service-c           (2.1s) - 3 errors
  ...

Scan complete (48.3s)

  Projects scanned:     22
  Console errors:       47
  Console warnings:     132
  Critical issues:      4

Report written to: docs/reports/console_scans/CONSOLE_SCAN_20260107_143045.md

View report:
  cat docs/reports/console_scans/CONSOLE_SCAN_20260107_143045.md

Critical projects (need attention):
  • service-a - landing: 12 errors, product_app: timeout
  • web-app - product_app: 5 errors
  • example-project - product_app: Auth0 configuration missing
  • api-service - landing: 2 errors, product_app: 3 errors
```

## Report Format

### Markdown Report Structure

```markdown
# Console Scan Report

## Summary
- Total Errors: 47
- Total Warnings: 132
- Critical Projects: 4

## Critical Issues

### Service-a
**Landing** (https://service-a.example.com/)
- [ERROR] Uncaught TypeError: Cannot read properties... (×8) - `Button.tsx:1234`
- [ERROR] Failed to load /assets/logo.png (404) (×5)

**Product** (https://app.service-a.example.com/)
- ❌ Timeout after 30s

## All Projects

### Service-b ✓
**Landing**: Clean
**Product**: 2 warnings (React deprecation)

### Service-c ⚠️
...

## Cross-Project Patterns

### Pattern 1: Auth0 configuration error
Affected projects (8): web-app, service-c, example-project, api-service, service-d, service-e, service-f, service-g
```

### JSON Export Format

```json
{
  "timestamp": "2026-01-07T14:30:45",
  "projects": {
    "service-b": {
      "status": "healthy",
      "total_errors": 0,
      "total_warnings": 2,
      "pages": [
        {
          "endpoint_type": "landing",
          "url": "https://service-b.example.com/",
          "success": true,
          "status_code": 200,
          "load_time_ms": 823,
          "error_count": 0,
          "warning_count": 2,
          "errors": [],
          "warnings": [
            {
              "message": "React does not recognize `customProp`...",
              "location": "Component.tsx:123",
              "count": 10
            }
          ]
        }
      ]
    }
  }
}
```

## Console Message Processing

### Truncation & Deduplication

**Before Processing** (verbose stack trace):
```
[ERROR] Uncaught TypeError: Cannot read properties of undefined (reading 'x')
    at Object.handleClick (webpack://myapp/./src/components/Button.tsx?:1234:56)
    at onClick (webpack://myapp/./node_modules/react-dom/cjs/react-dom.production.min.js:123:456)
    ... (100+ lines)
```

**After Processing** (compact):
```
[ERROR] Uncaught TypeError: Cannot read properties of undefined (reading 'x') (×8)
Location: Button.tsx:1234
```

### Features

- ✅ Truncate messages to 150 characters
- ✅ Extract file:line from stack traces
- ✅ Deduplicate identical errors (show count)
- ✅ Filter common noise (HMR, DevTools, etc.)
- ✅ Store full text for detailed reports
- ✅ Sort by severity (error > warning > info)

### Ignored Patterns (Configurable)

Default ignore list:
- "Download the React DevTools"
- "React Router Future Flag Warning"
- "Source map could not be loaded"
- "[HMR]" (Hot Module Replacement)
- "[webpack-dev-server]"
- "Slow network is detected"

## Command Reference

### Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--all` | Scan all portfolio projects | - |
| `-p, --project` | Specific project(s) | - |
| `--domain-type` | production or internal | production |
| `--endpoint-type` | landing, product_app, or both | both |
| `--instance` | Filter to EC2 instance (1, 2, or 3) | all |

### Dashboard Mode Options

| Option | Description |
|--------|-------------|
| `--dashboard` | Enable dashboard mode |
| `--compact` | Show compact summary |

### Report Mode Options

| Option | Description | Default |
|--------|-------------|---------|
| `--report` | Enable report mode | - |
| `--detail` | minimal, summary, or full | summary |
| `--json` | JSON export instead of markdown | false |
| `--headed` | Show browser (debugging) | false |
| `--screenshot-errors` | Capture error screenshots | true |
| `--timeout` | Page load timeout (seconds) | 30 |
| `-o, --output` | Report output directory | docs/reports/console_scans |

## Workflows

### Daily Health Check

```bash
# Quick morning check
sega probe scan --dashboard --all

# If issues found, deep dive
sega probe scan -p <problematic-project> --report --detail full
```

### Pre-Deployment Validation

```bash
# Full scan before pushing to production
sega probe scan --all --report --domain-type production

# Review critical issues
cat docs/reports/console_scans/CONSOLE_SCAN_*.md
```

### CI/CD Integration

```bash
# Exit with error code if critical issues found
sega probe scan --all --report --json > scan_results.json

# Parse results programmatically
jq '.projects | to_entries[] | select(.value.status == "critical")' scan_results.json
```

### Cross-Project Error Analysis

```bash
# Generate report
sega probe scan --all --report

# Review "Cross-Project Patterns" section
# Identify systemic issues (Auth0, CORS, etc.)
```

## Performance

| Operation | Duration | Notes |
|-----------|----------|-------|
| Dashboard (all 22) | 2-3s | HTTP requests only |
| Dashboard (instance 1) | 1-2s | ~11 projects |
| Console scan (1 project) | 2-4s | 2 pages × 1-2s each |
| Console scan (all 22) | 60-90s | Parallel browser instances |
| Report generation | <1s | Markdown + JSON |

## Troubleshooting

### Playwright Not Installed

```bash
$ sega probe scan --all --report

Missing dependency: Playwright not installed

Install Playwright:
  pip install playwright && playwright install
```

**Fix**:
```bash
pip install playwright
playwright install
```

### Timeout Errors

If pages timeout frequently, increase timeout:

```bash
sega probe scan --all --report --timeout 60
```

### Memory Issues

For large scans (all 22 projects), run in batches:

```bash
sega probe scan --instance 1 --report
sega probe scan --instance 2 --report
```

## Next Steps

1. **Run dashboard check**: `sega probe scan --dashboard --all`
2. **If critical issues**: `sega probe scan --all --report`
3. **Review report**: `cat docs/reports/console_scans/CONSOLE_SCAN_*.md`
4. **Fix issues** based on report recommendations
5. **Re-scan**: Verify fixes resolved errors

## Related Documentation

- [Probe Command Reference](../reference/cli-reference.md#sega-probe)
- [Domain Test Runner](../architecture/domain-testing.md)
- [Domain Registry](../../docs/architecture/infrastructure/dns/DOMAIN_REGISTRY.md)
- [Port Allocation Standards](../../docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md)
