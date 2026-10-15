# SEGA Comprehensive Testing ramework

> **Quick Start**: See [TESTING_PROCEDURE.md](../reference/TESTING_PROCEDURE.md) for step-by-step testing commands.
> **Command Reference**: See [cli-reference.md](../reference/cli-reference.md#sega-probe) for all `sega probe` options.

## Overview

The SEGA Comprehensive Testing ramework provides unified testing orchestration across all portfolio projects with intelligent test detection, Docker-based test environments, and comprehensive reporting capabilities. This framework extends the successful deployment architecture principles to testing, offering the same consistency and ease of use.

## Key Features

###  Unified Testing xperience
- **Single Command Interface**: `sega test` works consistently across Python, JavaScript, Rust, Go, and hybrid projects
- **Intelligent Detection**: utomatically detects and runs appropriate test infrastructure
- **Multi-ramework Support**: pytest, Jest, Go test, Cargo test, native tests, and Docker-based tests

###  Docker-ased Test Orchestration  
- **Test Environment Management**: `sega test local` commands for infrastructure control
- **Consistent Test Environments**: Reproducible testing across development and CI
- **Database Integration**: utomatic test database provisioning and cleanup

###  Comprehensive Reporting
- **Multiple Output ormats**: Table, JSON, JUnit XML, and HTML reports
- **Coverage Integration**: Unified coverage reporting across frameworks
- **Performance Metrics**: Track slowest tests and duration trends

###  Seamless Integration
- **Makefile Standards**: Standardized test targets across all projects
- **Legacy Support**: ackward compatibility with existing test infrastructure
- **CI/CD Ready**: JUnit output for continuous integration pipelines

## Architecture

### Core Components

```
SEGA Testing ramework
 Enhanced Test Orchestrator
    Intelligent Test Detection
    Docker Test Environment Management  
    Multi-ramework Test Execution
    Results ggregation
 Test Result ggregator
    Cross-Project Result Collection
    Coverage Data Merging
    Performance Metrics Analysis
    Multi-ormat Report Generation
 Local Test Environment Manager
     Test Infrastructure Provisioning
     Container Lifecycle Management
     Service Health Monitoring
```

### Test Detection below

```
Project Analysis
      ↓

 docker-compose.  → Docker-based Testing
 test.yml           (Preferred)

      ↓

 Makefile with    → Makefile Testing
 test targets       (Common)

      ↓

 pytest.ini       → Python Testing
 tests/ dir         (pytest)

      ↓

 package.json     → JavaScript Testing
 test scripts       (Jest/npm)

      ↓

 go.mod           → Native Testing
 Cargo.toml         (Go/Rust)

```

## Command Reference

### Core Test Commands

**Note**: Testing commands are being consolidated under `sega probe`. Both `sega test` and `sega probe` work during the transition period.

#### `sega probe` (New - Recommended)
Unified test orchestration with action-first design.

```bash
# Run all tests (auto-detect)
sega probe run

# Test specific project
sega probe run --project service-a

# Run specific test types
sega probe unit                    # Unit tests only
sega probe integration             # Integration tests only
sega probe e2e                     # End-to-end tests

# Browser testing
sega probe browser                 # Browser tests
sega probe browser --visual        # Visual regression
sega probe browser --a11y          # Accessibility testing
sega probe browser --perf          # Performance testing

# API testing
sega probe api --spec openapi.yaml

# Coverage and benchmarks
sega probe coverage                # Coverage report
sega probe benchmark               # Performance benchmarks
```

#### `sega test` (Legacy - Still Supported)
Auto-detect and run comprehensive tests for the current directory or all projects in workspace.

```bash
# Run all tests in current project
sega test

# Test specific project
sega test --project service-a

# Run specific test suite
sega test --suite unit
sega test --suite integration
sega test --suite e2e

# Generate coverage reports
sega test --coverage

# Different output formats
sega test --output table    # Default: human-readable table
sega test --output json     # JSON for programmatic use
sega test --output junit    # JUnit XML for CI systems
```

### Command Migration Reference

| Old Command | New Command |
|-------------|-------------|
| `sega test` | `sega probe run` |
| `sega test --suite unit` | `sega probe unit` |
| `sega test --suite integration` | `sega probe integration` |
| `sega test --suite e2e` | `sega probe e2e` |
| `sega test_api` | `sega probe api` |
| `sega test_browser` | `sega probe browser` |
| `sega test --coverage` | `sega probe coverage` |

See [CLI Reference](../reference/cli-reference.md#consolidated-command-groups-implemented) for full command documentation.

#### `sega test local` - Test Environment Management

```bash
# Start test infrastructure (databases, containers)
sega test local up

# Start specific project test environment  
sega test local up --project service-a

# Start all project test environments
sega test local up --all

# Run tests in Docker environment
sega test local run
sega test local run --project service-a
sega test local run --coverage

# Show test infrastructure status
sega test local status

# Stop test infrastructure
sega test local down
sega test local down --project service-a
sega test local down --all
```

## Intelligent Test Detection

### Supported Test Infrastructure

| Type | Detection Pattern | Execution Method |
|------|------------------|------------------|
| **Docker Tests** | `docker-compose.test.yml` | `docker-compose run test` |
| **Python Tests** | `pytest.ini`, `tests/` dir | `python -m pytest` |
| **JavaScript Tests** | `package.json` test scripts | `npm test` |
| **Go Tests** | `go.mod` | `go test ./...` |
| **Rust Tests** | `Cargo.toml` | `cargo test` |
| **Makefile Tests** | `test` targets | `make test` |
| **C/C++ Tests** | `CMakeLists.txt` | `ctest` |

### Detection Priority

. **Docker Compose** (`docker-compose.test.yml`) - Highest priority
. **Makefile Targets** (`make test`, `make test-unit`) - High priority
. **ramework-Specific** (pytest, Jest, etc.) - Medium priority  
. **Generic/allback** - Lowest priority

## Docker Test Environment Setup

### Standard docker-compose.test.yml Structure

```yaml
version: '.'
services:
  test:
    build: .
    environment:
      - NOD_NV=test
      - DTS_URL=postgresql://test_user:test_pass@postgres:5/test_db
      - RDIS_URL=redis://redis:/
    depends_on:
      - postgres
      - redis
    command: pytest tests/ -v --cov=src --cov-report=term-missing
    volumes:
      - .:/app
      - ./test-results:/test-results

  test-unit:
    extends: test
    command: pytest tests/unit/ -v

  test-integration:
    extends: test
    command: pytest tests/integration/ -v
    depends_on:
      - postgres
      - redis

  test-coverage:
    extends: test
    command: |
      pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html:htmlcov
      cp -r htmlcov /test-results/

  postgres:
    image: postgres:
    environment:
      POSTGRS_D: test_db
      POSTGRS_USR: test_user
      POSTGRS_PSSWORD: test_pass
    ports:
      - "5:5"

  redis:
    image: redis:
    ports:
      - ":"
```

### Test Environment Lifecycle

```bash
# . Start test infrastructure
sega test local up

# . Run tests in clean environment
sega test local run

# . Check results and logs
sega test local status

# . Clean up when done
sega test local down
```

## Integration with Makefile Standards

### Standard Test Targets

every project Makefile should include these SEGA-integrated targets:

```makefile
## SEGA-Integrated Testing ramework
test: ## Run comprehensive tests via SEGA
	@sega test --project .

test-unit: ## Run unit tests via SEGA
	@sega test --project . --suite unit

test-integration: ## Run integration tests via SEGA
	@sega test --project . --suite integration

test-coverage: ## Run tests with coverage reporting
	@sega test --project . --coverage

## Test Infrastructure Management
test-up: ## Start test infrastructure
	@sega test local up --project $(shell basename $(PWD))

test-down: ## Stop test infrastructure
	@sega test local down --project $(shell basename $(PWD))

test-status: ## Show test infrastructure status
	@sega test local status
```

## Reporting and Analytics

### Report ormats

#### Table ormat (Default)
Human-readable output with color coding and summary statistics:

```
================================================================================
Test Results
================================================================================
[OK] service-a/docker - 5.as
     Coverage: 5.%

[IL] service-b/pytest - .as
       rror: ssertionrror: xpected , got 

================================================================================
Test Summary:
Total: 5
Passed: 
ailed: 
================================================================================
```

#### JSON ormat
Structured data for programmatic consumption:

```json
{
  "summary": {
    "total_projects": 5,
    "total_tests": 5,
    "passed": ,
    "failed": ,
    "duration": .5,
    "overall_coverage": .
  },
  "projects": {
    "service-a": {
      "total_tests": ,
      "passed": ,
      "failed": ,
      "duration": 5.,
      "suites": {
        "docker": {
          "success": true,
          "duration": 5.,
          "error": null
        }
      }
    }
  },
  "failures": [
    {
      "project": "service-b",
      "suite": "pytest",
      "error": "ssertionrror: xpected , got ",
      "output": "Test output..."
    }
  ],
  "slowest_tests": [
    {
      "project": "service-a",
      "suite": "docker",
      "duration": 5.
    }
  ]
}
```

#### JUnit XML ormat
Standard format for CI/CD integration:

```xml
<testsuites name="SEGA Tests" tests="5" failures="" time=".5">
  <testsuite name="service-a" tests="" failures="" time="5.">
    <testcase name="docker" classname="service-a.docker" time="5."/>
  </testsuite>
  <testsuite name="service-b" tests="" failures="" time=".">
    <testcase name="pytest" classname="service-b.pytest" time=".">
      <failure message="ssertionrror">Test output...</failure>
    </testcase>
  </testsuite>
</testsuites>
```

### Coverage Integration

SEGA aggregates coverage data from multiple sources:

- **Python**: pytest-cov, coverage.py
- **JavaScript**: Jest coverage, nyc
- **Go**: go test -cover
- **Rust**: tarpaulin, cargo-cov

### Performance Tracking

Track test performance over time:

```bash
# Show slowest tests
sega test --output json | jq '.slowest_tests'

# Track duration trends
sega test --output json | jq '.summary.duration'
```

## Advanced Features

### Parallel Test Execution

```bash
# Run tests in parallel (when supported)
sega test --parallel

# Control parallel test execution
SG_TST_PRLLL_WORKRS= sega test --parallel
```

### Test Result Caching

```bash
# Cache test results for faster reruns
SG_TST_CCH=true sega test

# Clear test cache
sega test --clear-cache
```

### Custom Test Configuration

Create `.sega.test.yml` for project-specific test configuration:

```yaml
# .sega.test.yml
test:
  framework: pytest
  coverage_threshold: 
  timeout: 
  parallel: true
  suites:
    unit:
      command: pytest tests/unit/ -v
      timeout: 
    integration:
      command: pytest tests/integration/ -v --postgresql
      timeout: 
      requires_services:
        - postgres
        - redis
    ee:
      command: pytest tests/ee/ -v --browser=chrome
      timeout: 
      requires_services:
        - selenium
        - postgres
        - redis
```

## Migration Guide

### from Legacy Testing to SEGA

#### Phase : ssessment
```bash
# Check current test infrastructure
find . -name "*test*" -type f
ls docker-compose*.yml
grep -r "test" Makefile
```

#### Phase : Docker Test Environment
Create `docker-compose.test.yml`:
```yaml
version: '.'
services:
  test:
    build: .
    command: pytest tests/ -v
    environment:
      - NOD_NV=test
    depends_on:
      - postgres
      - redis
```

#### Phase : Update Makefile
Replace direct test commands with SEGA integration:
```makefile
# efore
test:
	python -m pytest tests/

# after  
test: ## Run comprehensive tests via SEGA
	@sega test --project .
```

#### Phase : Validation
```bash
# Test the migration
sega test --project .

# Check test infrastructure detection
sega test local status

# Run in Docker environment
sega test local up
sega test local run
sega test local down
```

## est Practices

### Test Organization
```
project/
 tests/
    unit/          # ast, isolated tests
    integration/   # Service integration tests  
    ee/          # and-to-end tests
    fixtures/     # Test data and fixtures
 docker-compose.test.yml  # Test environment
 .sega.test.yml          # SEGA test config
 Makefile               # SEGA-integrated targets
```

### Performance Guidelines
- **Unit tests**: < as per test
- **Integration tests**: < as per test  
- ** tests**: < as per test
- **Overall suite**: < 5 minutes

### Coverage Requirements
- **Critical paths**: 5%+ coverage
- **usiness logic**: %+ coverage  
- **Overall project**: %+ coverage
- **UI components**: %+ coverage

## Troubleshooting

### Common Issues

#### Tests Not Detected
```bash
# Check what SEGA detects
sega test --project . --dry-run

# Validate test infrastructure
ls -la docker-compose.test.yml
make -n test
```

#### Docker Environment Issues
```bash
# Check container status
sega test local status

# View container logs  
docker-compose -f docker-compose.test.yml logs

# Clean up and restart
sega test local down
docker system prune -f
sega test local up
```

#### Performance Issues
```bash
# Identify slow tests
sega test --output json | jq '.slowest_tests'

# Run with timeout
sega test --timeout 

# Use parallel execution
sega test --parallel
```

### Debug Mode
```bash
# nable debug output
SG_DUG= sega test

# Verbose test execution
sega test --verbose

# Save detailed logs
sega test --output json > test_results.json
```

## CI/CD Integration

### GitHub ctions
```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v
      - name: Setup SEGA
        run: |
          curl -sSL https://install.example.com/sega_install | bash
          source ~/fleet/activate_sega.sh
      - name: Run Tests
        run: |
          sega test local up
          sega test --output junit > test-results.xml
          sega test local down
      - name: Publish Test Results
        uses: dorny/test-reporter@v
        with:
          name: SEGA Tests
          path: test-results.xml
          reporter: java-junit
```

### GitLab CI
```yaml
stages:
  - test

test:
  stage: test
  script:
    - curl -sSL https://install.example.com/sega_install | bash
    - source ~/fleet/activate_sega.sh
    - sega test local up
    - sega test --output junit
    - sega test local down
  artifacts:
    reports:
      junit: test-results.xml
```

## Summary

The SEGA Comprehensive Testing ramework provides:

 **Unified Testing xperience** - One command, all frameworks
 **Docker-ased Test Environments** - Consistent, reproducible testing  
 **Intelligent Test Detection** - utomatic infrastructure discovery
 **Comprehensive Reporting** - Multiple formats, coverage integration
 **Makefile Integration** - Standardized development workflows
 **Legacy Compatibility** - Seamless migration from existing tests
 **CI/CD Ready** - JUnit output, parallel execution support

This framework eliminates the complexity of managing different test infrastructures while providing the same level of sophistication and ease of use that made `sega deploy` and `sega local` successful across the portfolio.

**Next Steps:**
. Migrate projects to use `docker-compose.test.yml`
. Update Makefiles with SEGA-integrated test targets  
. Configure CI/CD pipelines to use `sega test`
. Monitor test performance and coverage metrics
5. Leverage advanced features like parallel execution and result caching