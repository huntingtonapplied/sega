# Testing Procedure Reference

**Purpose**: Sequential testing procedure from simple to complex, covering all testing architectures and tools across your projects.

**Principle**: Start with fast, simple tests. Progress to complex, comprehensive tests. Fail fast to save time.

---

## Testing Levels Overview

| Level | Type | Duration | Purpose |
|-------|------|----------|---------|
| 1 | Health Checks | ~5s | Verify services are running |
| 2 | Unit Tests | ~30s | Isolated function/component tests |
| 3 | API Endpoint Tests | ~1-2min | Validate API contracts |
| 4 | Integration Tests | ~2-5min | Service interaction tests |
| 5 | Frontend Route Tests | ~2-5min | Route rendering verification |
| 6 | Browser Tests | ~5-10min | UI interaction tests |
| 7 | E2E Tests | ~10-20min | Full workflow validation |
| 8 | Load/Performance Tests | ~30min+ | Capacity and stress testing |

---

## Level 1: Health Checks (Fastest)

**Purpose**: Verify backend services are running and responding.

### Quick Health Check (All Projects)
```bash
# Check all projects via SEGA
sega test-api --health-only

# Check specific projects
sega test-api --health-only service-a service-b service-c

# Check remote host (EC2)
sega test-api --health-only --host 203.0.113.10
```

### Single Project Health Check
```bash
# Using curl directly
curl -s http://localhost:8001/health | jq .

# Using SEGA health command
sega health --project my-project

# Wait for service to become healthy
sega health --project my-project --wait --timeout 60
```

### Standard Health Endpoints (Per Project Type)
| Project Type | Endpoint | Expected Response |
|--------------|----------|-------------------|
| Backend/API | `/health` | `{"status": "healthy"}` |
| With Database | `/health` | `{"status": "healthy", "database": "connected"}` |
| Auth0 Enabled | `/api/auth0/health` | `{"status": "ok"}` |

---

## Level 2: Unit Tests

**Purpose**: Fast, isolated tests that don't require external services.

### Run Unit Tests via SEGA Probe
```bash
# Auto-detect and run unit tests
sega probe unit

# Specific project
sega probe unit --project-path ~/portfolio/my-project

# With coverage
sega probe unit --coverage
```

### Direct Framework Commands
```bash
# Python (pytest)
cd ~/portfolio/my-project && python -m pytest tests/unit/ -v

# JavaScript (Jest)
cd ~/portfolio/web-app/frontend && npm test

# Go
cd ~/portfolio/api-service && go test ./...

# Rust
cd ~/portfolio/engine-service && cargo test
```

### Makefile Targets
```bash
# Standard target (most projects)
make test-unit

# With coverage
make test-coverage
```

---

## Level 3: API Endpoint Tests

**Purpose**: Validate API contracts and endpoint behavior.

### Basic API Testing
```bash
# Test all endpoints against running services
sega test-api

# Test specific projects
sega test-api my-project service-b service-e

# Quick test with timeout
sega test-api --timeout 5
```

### OpenAPI Discovery Testing
```bash
# Auto-discover endpoints from OpenAPI schema
sega test-api --discover my-project

# Discover and run intelligent test chains
sega test-api --discover --chain my-project

# Run chains in parallel
sega test-api --discover --chain --parallel my-project service-b
```

### Authentication Modes for API Tests
```bash
# No authentication (public endpoints)
sega test-api --auth none my-project

# Mock JWT (test mode - requires SEGA_TEST_MODE=true on backend)
sega test-api --auth mock my-project

# Real token from environment
export SEGA_TEST_AUTH_TOKEN="your-token"
sega test-api --auth real my-project

# Show auth info before testing
sega test-api --show-auth --auth mock my-project
```

### Direct API Testing with curl
```bash
# Simple endpoint test
curl -s http://localhost:8004/api/v1/simulations | jq .

# With authentication
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8004/api/v1/simulations | jq .

# POST request
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"name": "test"}' \
  http://localhost:8004/api/v1/simulations | jq .
```

### Project Render Verification
```bash
# Verify deployed project endpoints using laboratory config
python ~/portfolio/sega/scripts/testing/verify_project_render.py web-app

# Test all projects
~/portfolio/sega/scripts/testing/test_all_projects_render.sh
```

---

## Level 4: Integration Tests

**Purpose**: Test service interactions and database operations.

### Run Integration Tests
```bash
# Via SEGA probe
sega probe integration

# Specific project
sega probe integration --project-path ~/portfolio/my-project
```

### Docker-Based Integration Tests
```bash
# Start test infrastructure
sega test local up

# Run tests in Docker environment
sega test local run --project my-project

# Run with specific suite
sega test local run --suite integration

# Stop test infrastructure
sega test local down
```

### Direct Integration Test Commands
```bash
# Python
python -m pytest tests/integration/ -v

# With database
python -m pytest tests/integration/ -v --postgresql

# With Redis
python -m pytest tests/integration/ -v --redis
```

### Infrastructure Status Check
```bash
# Check test infrastructure status
sega test local status

# View container logs
docker-compose -f docker-compose.test.yml logs
```

---

## Level 5: Frontend Route Tests

**Purpose**: Verify Next.js routes render correctly with actual content.

### What Gets Verified
- **HTTP Status**: 200, redirects (301/302/307/308), errors
- **Content Size**: Line count and byte count for each route
- **Empty Detection**: Flags 200 responses with 0 lines or <100 bytes as failures
- **Saved Output**: HTML saved to `/tmp/page_{route}_{port}.html` for inspection

### Frontend Route Testing Scripts
```bash
cd ~/portfolio/sega/scripts/testing/frontend-testing

# List routes only (no servers started)
./check-frontend-routes.sh --routes ~/portfolio/web-app/frontend

# List routes for specific app (landing or product)
./check-frontend-routes.sh --routes ~/portfolio/api-service/frontend --app landing
./check-frontend-routes.sh --routes ~/portfolio/api-service/frontend --app product
```

### Serve and Test
```bash
# Start servers only (manual browser testing)
./check-frontend-routes.sh --serve ~/portfolio/web-app/frontend

# Live test (start servers + test all routes)
./check-frontend-routes.sh --live ~/portfolio/web-app/frontend

# Dry run (preview what will be tested)
./check-frontend-routes.sh --live ~/portfolio/web-app/frontend --dry-run
```

### Design Staging Routes (iteration2 architecture)
```bash
# Test iteration2 (dual-app) architecture
./check-frontend-routes.sh --routes ~/portfolio/design/integration_staging/projects/web-app/iteration2
./check-frontend-routes.sh --live ~/portfolio/design/integration_staging/projects/api-service/iteration2

# Test specific app in dual-app setup
./check-frontend-routes.sh --live ~/portfolio/design/integration_staging/projects/api-service/iteration2 --app product
```

### Custom Ports
```bash
# Override default ports
./check-frontend-routes.sh --serve ~/portfolio/web-app/frontend \
  --landing-port 4000 --product-port 4001
```

### Port Reference
| App Type | Default Port |
|----------|-------------|
| Landing App | 3000 |
| Product App | 3001 |
| Single App | 3010 |

---

## Level 6: Browser Tests

**Purpose**: Test UI interactions via Playwright.

### Basic Browser Testing
```bash
# Run browser tests
sega probe browser

# Specific project
sega probe browser --project my-project

# Headed mode (visible browser)
sega probe browser --headed
```

### Specialized Browser Tests
```bash
# Visual regression testing (screenshot comparison)
sega probe browser --visual

# Accessibility testing (WCAG compliance)
sega probe browser --a11y

# Performance testing (Core Web Vitals)
sega probe browser --perf
```

### Browser Selection
```bash
# Chromium (default)
sega probe browser --browser chromium

# Firefox
sega probe browser --browser firefox

# WebKit (Safari)
sega probe browser --browser webkit
```

### Three-Tier Browser Validation
```bash
# Legacy command (still supported)
sega test browser --project service-a --type validation

# With data management
sega test browser --project service-a --reset-data --create-user

# CRUD workflow testing
sega test browser --project service-a --crud-workflow
```

**Validation Tiers**:
- **Tier 1 (Static)**: App startup, frontend rendering, navigation, core routes
- **Tier 2 (Dynamic)**: API + UI integration with CRUD workflows
- **Tier 3 (Integration)**: Authentication, real-time features, cross-service calls

### Project Setup for Browser Tests
```bash
# Initialize browser testing for any project
~/portfolio/sega/templates/browser/setup-browser-testing.sh myproject
```

---

## Level 7: End-to-End Tests

**Purpose**: Full workflow validation across all layers.

### Run E2E Tests
```bash
# Via SEGA probe
sega probe e2e

# Headed mode for debugging
sega probe e2e --headed

# Specific project
sega probe e2e --project-path ~/portfolio/my-project
```

### Full Stack Verification Pattern
```bash
# 1. Start all services
sega local up -p my-project

# 2. Verify backend
sega health --project my-project --wait

# 3. Run API tests
sega test-api my-project

# 4. Run frontend route tests
~/portfolio/sega/scripts/testing/frontend-testing/check-frontend-routes.sh --live ~/portfolio/my-project/frontend

# 5. Run E2E tests
sega probe e2e --project-path ~/portfolio/my-project

# 6. Stop services
sega local down -p my-project
```

### Docker E2E Environment
```bash
# Full environment with E2E
sega test local up --all
sega test local run --suite e2e
sega test local down --all
```

---

## Level 8: Load & Performance Tests

**Purpose**: Capacity, stress, and chaos testing.

### Load Testing
```bash
# Run load tests
sega probe benchmark --iterations 10

# Custom load test configuration
# Create load_test_config.json:
{
  "target_url": "http://localhost:8004",
  "concurrent_users": 50,
  "duration": 120,
  "ramp_up_time": 10
}
```

### Security Testing
```bash
# Security scan
sega doctor scan --type code

# Secrets scan
sega doctor scan --type secrets

# Dependency vulnerability scan
sega doctor scan --type deps
```

### Chaos Testing
```bash
# Chaos engineering tests (requires Kubernetes)
# Configure chaos_test_config.json:
{
  "target_namespace": "sega-deployments",
  "duration": 300,
  "experiments": ["pod_failure", "network_delay", "cpu_stress"]
}
```

---

## Complete Testing Workflow (Sequential)

### Pre-Push Validation
```bash
#!/bin/bash
# Run before pushing code

PROJECT=${1:-$(basename $(pwd))}

echo "=== Level 1: Health Check ==="
sega health --project $PROJECT || exit 1

echo "=== Level 2: Unit Tests ==="
sega probe unit || exit 1

echo "=== Level 3: API Tests ==="
sega test-api --health-only $PROJECT || exit 1

echo "All pre-push tests passed!"
```

### Full CI Validation
```bash
#!/bin/bash
# Complete CI testing sequence

PROJECT=${1:-$(basename $(pwd))}

echo "=== Starting Test Infrastructure ==="
sega test local up

echo "=== Level 1: Health Checks ==="
sega health --project $PROJECT --wait --timeout 60

echo "=== Level 2: Unit Tests ==="
sega probe unit --coverage

echo "=== Level 3: API Tests ==="
sega test-api --discover --chain $PROJECT

echo "=== Level 4: Integration Tests ==="
sega probe integration

echo "=== Level 5: Frontend Routes ==="
~/portfolio/sega/scripts/testing/frontend-testing/check-frontend-routes.sh --routes ~/portfolio/$PROJECT/frontend

echo "=== Level 6: Browser Tests ==="
sega probe browser --a11y

echo "=== Level 7: E2E Tests ==="
sega probe e2e

echo "=== Cleanup ==="
sega test local down

echo "All tests passed!"
```

---

## Project-Specific Testing

### Simulation Projects (my-project, service-d, service-e, etc.)
```bash
# These have engines that need special testing
sega local up -p my-project --shared engine
sega probe run --platform api
sega probe e2e
```

### Frontend-Heavy Projects (web-app, api-service, service-l, service-m)
```bash
# Emphasis on route and browser testing
./check-frontend-routes.sh --live ~/portfolio/$PROJECT/frontend
sega probe browser --visual --a11y
```

### Infrastructure Projects (sega, service-a, engine-service)
```bash
# CLI and system testing focus
cargo test  # or go test ./...
sega probe unit
sega probe integration
```

---

## Quick Reference Commands

| Goal | Command |
|------|---------|
| Check if service running | `sega health --project NAME` |
| Run unit tests | `sega probe unit` |
| Run all tests | `sega probe run` |
| Test API endpoints | `sega test-api PROJECT` |
| Auto-discover APIs | `sega test-api --discover PROJECT` |
| Test frontend routes | `./check-frontend-routes.sh --live PATH` |
| Run browser tests | `sega probe browser` |
| Visual regression | `sega probe browser --visual` |
| Run E2E tests | `sega probe e2e` |
| Coverage report | `sega probe coverage` |
| Start test infra | `sega test local up` |
| Stop test infra | `sega test local down` |

---

## Output Formats

### Table (Default - Human Readable)
```bash
sega probe run
```

### JSON (Programmatic)
```bash
sega probe run --output json | jq .
sega test-api --json PROJECT
```

### JUnit XML (CI/CD)
```bash
sega test --output junit > test-results.xml
```

---

## Troubleshooting

### Service Not Responding
```bash
# Check container status
docker ps
sega local status

# Check logs
sega local logs PROJECT
docker-compose logs backend
```

### Tests Not Detected
```bash
# Check what SEGA detects
sega probe run --verbose

# Verify test infrastructure exists
ls -la docker-compose.test.yml
ls -la tests/
```

### Database Connection Issues
```bash
# Verify database is running
docker ps | grep postgres

# Check connection
sega health --project PROJECT --verbose
```

### Frontend Not Loading
```bash
# Check if node_modules exists
ls -la frontend/node_modules

# Use shared node_modules
sega local up -p PROJECT --shared frontend
```

---

## Related Documentation

- [CLI Reference](cli-reference.md) - Full command documentation
- [Testing Framework](../development/SEGA_TESTING_FRAMEWORK.md) - Framework details
- [Browser Testing Validation](../../tests/BROWSER_TESTING_VALIDATION_REPORT.md) - Browser test report
- [Frontend Testing README](../../scripts/testing/frontend-testing/README.md) - Route testing guide

---

*Last Updated*: 2025-12-21
*Maintained By*: SEGA Infrastructure
