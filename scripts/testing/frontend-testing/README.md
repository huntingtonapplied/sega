# SEGA Frontend Testing

**Location**: `sega/scripts/testing/frontend-testing/`
**Purpose**: Frontend route verification and live testing for managed projects
**Integration**: Complements SEGA's backend testing (`sega test`, `verify_project_render.py`)

---

## Overview

Frontend testing tools for verifying Next.js routes across all managed projects. These scripts integrate with SEGA's testing infrastructure to provide full-stack verification.

---

## Quick Reference

```bash
cd ~/workspace/sega/scripts/testing/frontend-testing

# List routes only (no servers)
./check-frontend-routes.sh --routes <path>
./check-frontend-routes.sh --routes <path> --app landing
./check-frontend-routes.sh --routes <path> --app product

# Start servers only (no testing)
./check-frontend-routes.sh --serve <path>
./check-frontend-routes.sh --serve <path> --app landing
./check-frontend-routes.sh --serve <path> --app product

# Live test (start servers + test routes)
./check-frontend-routes.sh --live <path>
./check-frontend-routes.sh --live <path> --app landing
./check-frontend-routes.sh --live <path> --app product
./check-frontend-routes.sh --live <path> --dry-run
```

---

## Available Scripts

### 1. check-frontend-routes.sh (Main Script)

Extracts, validates, and optionally live-tests Next.js routes.

**Supports:**
- Single-app architecture (iteration1)
- Dual-app architecture (iteration2/uix_split): landing_app + product_app
- Main project paths (`$FLEET_ROOT/$project/frontend`)
- Staging paths (`$FLEET_ROOT/design/integration_staging/projects/$project/iteration2`)

**Modes:**

| Mode | Flag | Description |
|------|------|-------------|
| Static Analysis | (none) | Analyze all projects in `$FLEET_ROOT/*/frontend` |
| Route Listing | `--routes` | List routes without starting servers |
| Serve Only | `--serve` | Start dev servers without testing |
| Live Testing | `--live` | Start servers and test all routes |

**Options:**

| Option | Values | Description |
|--------|--------|-------------|
| `--app` | `landing`, `product`, `both` | Filter which app(s) to process (default: both) |
| `--landing-port` | port number | Set landing app port (default: 3000) |
| `--product-port` | port number | Set product app port (default: 3001) |
| `--dry-run` | - | Preview what will be tested without starting servers |
| `-h`, `--help` | - | Show usage information |

### Usage Examples

```bash
cd ~/workspace/sega/scripts/testing/frontend-testing

# Static Analysis (batch mode - all projects)
./check-frontend-routes.sh                    # All projects
./check-frontend-routes.sh atlas              # Single project
./check-frontend-routes.sh atlas http://localhost:3001  # With health check

# Route Listing (no servers started)
./check-frontend-routes.sh --routes ~/workspace/design/integration_staging/projects/atlas/iteration2
./check-frontend-routes.sh --routes ~/workspace/design/integration_staging/projects/hermes/iteration2 --app product

# Serve Only (start servers, keep running until Ctrl+C)
./check-frontend-routes.sh --serve ~/workspace/design/integration_staging/projects/orion/iteration2
./check-frontend-routes.sh --serve ~/workspace/design/integration_staging/projects/atlas/iteration2 --app landing

# Live Testing (start servers + test routes)
./check-frontend-routes.sh --live ~/workspace/design/integration_staging/projects/atlas/iteration2
./check-frontend-routes.sh --live ~/workspace/design/integration_staging/projects/hermes/iteration2 --app product
./check-frontend-routes.sh --live ~/workspace/design/integration_staging/projects/orion/iteration2 --dry-run

# Custom ports
./check-frontend-routes.sh --serve ~/workspace/design/integration_staging/projects/atlas/iteration2 --landing-port 4000 --product-port 4001
./check-frontend-routes.sh --live ~/workspace/design/integration_staging/projects/hermes/iteration2 --app landing --landing-port 5000
```

---

## Project-Specific Commands

### Hermes
```bash
# Routes only
./check-frontend-routes.sh --routes ~/workspace/design/integration_staging/projects/hermes/iteration2

# Serve landing only
./check-frontend-routes.sh --serve ~/workspace/design/integration_staging/projects/hermes/iteration2 --app landing

# Live test product only
./check-frontend-routes.sh --live ~/workspace/design/integration_staging/projects/hermes/iteration2 --app product
```

### Atlas
```bash
# Routes only
./check-frontend-routes.sh --routes ~/workspace/design/integration_staging/projects/atlas/iteration2

# Serve both apps
./check-frontend-routes.sh --serve ~/workspace/design/integration_staging/projects/atlas/iteration2

# Live test all
./check-frontend-routes.sh --live ~/workspace/design/integration_staging/projects/atlas/iteration2
```

### Orion (iteration1)
```bash
./check-frontend-routes.sh --routes ~/workspace/design/integration_staging/archive/orion/iteration1
./check-frontend-routes.sh --live ~/workspace/design/integration_staging/archive/orion/iteration1
```

---

## Output Modes

### Route Listing (`--routes`)
- Lists all routes without starting servers
- Fast, no dependencies needed
- Useful for quick verification

### Serve Only (`--serve`)
- Starts Next.js dev server(s)
- Keeps running until Ctrl+C
- Useful for manual testing in browser

### Live Testing (`--live`)
- Auto-detects architecture (single-app vs dual-app)
- Starts Next.js dev servers on appropriate ports
- Tests all static routes via HTTP
- **Content verification**: Captures line count and byte count for each route
- **Empty detection**: Flags 200 responses with 0 lines or <100 bytes as failures
- **Saved output**: HTML saved to `/tmp/page_{route}_{port}.html` for inspection
- Handles redirects (301/302/307/308) as success
- Automatic cleanup on exit

**Output Format:**
| Status | Example Output |
|--------|----------------|
| Success | `✅ /dashboard (200, 45 lines, 12847 bytes)` |
| Empty/Minimal | `⚠️ /configurations (200 but 0 lines, 0 bytes - EMPTY/MINIMAL)` |
| Redirect | `↪️ /login (307 redirect, 5 lines)` |
| Failed | `❌ /missing (404, 12 lines)` |

**Ports Used:**
- Landing App: 3000
- Product App: 3001
- Single App: 3010

**Inspect Saved Pages:**
```bash
# After running --live, inspect saved HTML
ls -la /tmp/page_*.html
cat /tmp/page_dashboard_3001.html
```

---

## Integration with SEGA Testing

### Full-Stack Verification Pattern

```bash
# 1. Backend verification (SEGA)
cd ~/workspace/sega
python3 scripts/verify_project_render.py atlas

# 2. Frontend verification (SEGA frontend-testing)
~/workspace/sega/scripts/testing/frontend-testing/check-frontend-routes.sh --live ~/workspace/atlas/frontend
```

### SEGA Test Commands

| Command | Purpose |
|---------|---------|
| `sega test` | Run project test suites |
| `sega test --browser` | Browser-based testing |
| `sega test --api` | API endpoint testing |
| `verify_project_render.py` | Backend API verification |
| `check-frontend-routes.sh` | Frontend route verification |

---

## Related Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| Backend Verification | `sega/scripts/verify_project_render.py` | API endpoint testing |
| Multi-Project Render | `sega/scripts/test_all_projects_render.sh` | Batch backend testing |
| Customization Detection | `sega/scripts/testing/frontend-testing/detect_customization.sh` | Template diff analysis |

---

**Maintained By**: SEGA Infrastructure
**Updated**: 2025-12-10
