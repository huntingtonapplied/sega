# Makefile Standards with SEGA Integration

## Overview

This document defines the standardized Makefile structure and targets for all portfolio projects, with comprehensive SEGA testing framework integration. These standards ensure consistent development workflows across all project types while leveraging SEGA's intelligent test orchestration.

## Core Requirements

### . Standard Makefile Header

All Makefiles must begin with the following header:

```makefile
# Project Makefile
# Project: [PROJECT_NAME]
# SEGA-Integrated Development Workflow
# 
# Standard targets: dev, dev-shared, up, test, test-unit, test-integration, 
# test-coverage, clean, help
#
# for SEGA-specific commands:
# - sega test                  # auto-detect and run all tests
# - sega test --project .      # Test current project
# - sega test local up         # Start test infrastructure
# - sega test local run        # Run tests in Docker environment

.PHONY: help dev dev-shared up test test-unit test-integration test-e2e test-coverage test-up test-down test-status clean
.DEFAULT_GOAL := help
```

### . Standard Development Targets

#### Core Development Workflow

```makefile
## Development Workflow
dev: ## Start development environment (system Python + local npm + Docker databases)
	@echo "[INFO] Starting development environment..."
	@if [ -f "requirements.txt" ]; then \
		echo "[INFO] Installing Python dependencies..."; \
		pip install -r requirements.txt; \
	fi
	@if [ -f "package.json" ]; then \
		echo "[INFO] Installing Node dependencies..."; \
		npm install; \
	fi
	@$(MAKE) _start_databases
	@echo "[OK] Development environment ready"

dev-shared: ## Start development with shared dependencies (shared venv + shared node_modules + Docker databases)
	@echo "[INFO] Starting shared development environment..."
	@if [ -f "requirements.txt" ]; then \
		echo "[INFO] Using shared virtual environment..."; \
		source $(FLEET_VENV)/bin/activate && pip install -r requirements.txt; \
	fi
	@if [ -f "package.json" ]; then \
		echo "[INFO] Using shared node_modules..."; \
		ln -sf $(FLEET_NODE_MODULES) node_modules >/dev/null || npm install --prefix $(FLEET_NODE_MODULES)/.. && ln -sf $(FLEET_NODE_MODULES) node_modules; \
	fi
	@$(MAKE) _start_databases
	@echo "[OK] Shared development environment ready"

up: ## Start full Docker environment (production-like)
	@echo "[INFO] Starting full Docker environment..."
	@if [ -f "docker-compose.yml" ]; then \
		docker-compose up -d; \
	elif [ -f "deployment/docker-compose.yml" ]; then \
		docker-compose -f deployment/docker-compose.yml up -d; \
	else \
		echo "[ERROR] No docker-compose.yml found"; \
		exit 1; \
	fi
	@echo "[OK] Docker environment started"

_start_databases: ## Internal: Start database containers
	@echo "[INFO] Starting database containers..."
	@if [ -f "docker-compose.yml" ]; then \
		docker-compose up -d postgres redis timescaledb >/dev/null || echo "[INFO] Some databases not available"; \
	fi
```

## . SEGA-Integrated Testing Framework

### Standard Test Targets

```makefile
## SEGA-Integrated Testing Framework
test: ## Run comprehensive tests via SEGA (auto-detects test infrastructure)
	@echo "[INFO] Running SEGA comprehensive tests..."
	@sega test --project .
	@echo "[OK] Tests completed"

test-unit: ## Run unit tests via SEGA
	@echo "[INFO] Running unit tests..."
	@sega test --project . --suite unit
	@echo "[OK] Unit tests completed"

test-integration: ## Run integration tests via SEGA
	@echo "[INFO] Running integration tests..."
	@sega test --project . --suite integration
	@echo "[OK] Integration tests completed"

test-e2e: ## Run end-to-end tests via SEGA
	@echo "[INFO] Running e2e tests..."
	@sega test --project . --suite e2e
	@echo "[OK]  tests completed"

test-coverage: ## Run tests with coverage reporting via SEGA
	@echo "[INFO] Running tests with coverage..."
	@sega test --project . --coverage
	@echo "[OK] Coverage tests completed"
```

### Docker Test Environment Management

```makefile
## Test Infrastructure Management
test-up: ## Start test infrastructure (databases, containers)
	@echo "[INFO] Starting test infrastructure..."
	@sega test local up --project $(shell basename $(PWD))
	@echo "[OK] Test infrastructure ready"

test-down: ## Stop test infrastructure
	@echo "[INFO] Stopping test infrastructure..."
	@sega test local down --project $(shell basename $(PWD))
	@echo "[OK] Test infrastructure stopped"

test-status: ## Show test infrastructure status
	@echo "[INFO] Test infrastructure status:"
	@sega test local status

test-local: ## Run tests in Docker environment
	@echo "[INFO] Running tests in Docker environment..."
	@sega test local run --project $(shell basename $(PWD))
	@echo "[OK] Docker tests completed"
```

### Legacy Test Support (Fallback)

for projects that haven't fully migrated to SEGA, provide fallback targets:

```makefile
## Legacy Test Support (Fallback)
_test-legacy-python: ## Fallback: Python tests via pytest
	@echo "[INFO] Running Python tests (legacy)..."
	@if command -v python >/dev/null 2>&1; then \
		python -m pytest tests/ -v --tb=short; \
	else \
		echo "[ERROR] Python not available"; \
		exit 1; \
	fi

_test-legacy-node: ## Fallback: Node tests via npm
	@echo "[INFO] Running Node tests (legacy)..."
	@if command -v npm >/dev/null 2>&1 && [ -f "package.json" ]; then \
		npm test; \
	else \
		echo "[ERROR] npm not available for no package.json"; \
		exit 1; \
	fi

_test-legacy-docker: ## Fallback: Docker Compose tests
	@echo "[INFO] Running Docker tests (legacy)..."
	@if [ -f "docker-compose.test.yml" ]; then \
		docker-compose -f docker-compose.test.yml run --rm test; \
		docker-compose -f docker-compose.test.yml down -v; \
	else \
		echo "[ERROR] No docker-compose.test.yml found"; \
		exit 1; \
	fi
```

## . Standard Utility Targets

```makefile
## Utility Targets
clean: ## Clean build artifacts and containers
	@echo "[INFO] Cleaning build artifacts..."
	@rm -rf build/ dist/ *.egg-info/ .pytest_cache/ __pycache__/ .coverage htmlcov/
	@if command -v docker >/dev/null 2>&1; then \
		docker system prune -f; \
	fi
	@echo "[OK] Cleanup completed"

format: ## ormat code (if applicable)
	@echo "[INFO] ormatting code..."
	@if [ -f "requirements.txt" ] && command -v black >/dev/null 2>&1; then \
		black .; \
	fi
	@if [ -f "package.json" ] && command -v prettier >/dev/null 2>&1; then \
		npx prettier --write .; \
	fi
	@echo "[OK] Code formatted"

lint: ## Run linting (if applicable)
	@echo "[INFO] Running linters..."
	@if [ -f "requirements.txt" ] && command -v ruff >/dev/null 2>&1; then \
		ruff check src/; \
	fi
	@if [ -f "package.json" ] && command -v eslint >/dev/null 2>&1; then \
		npx eslint .; \
	fi
	@echo "[OK] Linting completed"

help: ## Show this help
	@echo "Project - Available Commands"
	@echo "================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "SEGA Test Commands:"
	@echo "  sega test                  # auto-detect and run all tests"
	@echo "  sega test --project .      # Test current project"
	@echo "  sega test --suite unit     # Run unit tests only"
	@echo "  sega test --coverage       # Run with coverage reporting"
	@echo "  sega test local up         # Start test infrastructure"
	@echo "  sega test local run        # Run tests in Docker environment"
	@echo "  sega test local status     # Show test infrastructure status"
```

## 5. Project-Specific Customizations

### Python Projects

```makefile
## Python-Specific Targets
install-python: ## Install Python dependencies
	@echo "[INFO] Installing Python dependencies..."
	@if [ -f "requirements.txt" ]; then \
		pip install -r requirements.txt; \
	fi
	@if [ -f "requirements-dev.txt" ]; then \
		pip install -r requirements-dev.txt; \
	fi

python-shell: ## Start Python shell with project context
	@echo "[INFO] Starting Python shell..."
	@python -i -c "print('Project shell ready')"
```

### Node.js Projects

```makefile
## Node.js-Specific Targets
install-node: ## Install Node dependencies
	@echo "[INFO] Installing Node dependencies..."
	@npm install

node-dev: ## Start Node development server
	@echo "[INFO] Starting Node development server..."
	@npm run dev
```

### Docker Projects

```makefile
## Docker-Specific Targets
build: ## build Docker images
	@echo "[INFO] uilding Docker images..."
	@if [ -f "docker-compose.yml" ]; then \
		docker-compose build; \
	elif [ -f "Dockerfile" ]; then \
		docker build -at $(shell basename $(PWD)) .; \
	fi

push: ## Push Docker images (requires registry configuration)
	@echo "[INFO] Pushing Docker images..."
	@echo "[WRNING] Registry push not implemented"
```

## . Integration with SEGA Test Framework

### Test Infrastructure Detection

SEGA automatically detects:
- `docker-compose.test.yml` files
- Makefile test targets
- pytest configuration
- Jest/npm test scripts
- Native test frameworks (Go, Rust, etc.)

### Enhanced Test Execution below

```
make test
    ↓
sega test --project .
    ↓
SEGA detects test infrastructure:
    - docker-compose.test.yml → Docker tests
    - Makefile test targets → Make tests  
    - pytest.ini → pytest
    - package.json scripts → npm test
    - go.mod → go test
    ↓
SEGA executes appropriate test runner
    ↓
Results aggregated and reported
```

## . Environment Variable Integration

```makefile
## Environment Variables
# Use portfolio standard environment variables
FLEET_ROOT ?= $(HOM)/fleet
FLEET_VENV ?= $(FLEET_ROOT)/venv
FLEET_NODE_MODULES ?= $(FLEET_ROOT)/node_modules
PROJECT_NAME ?= $(shell basename $(PWD))

# Test-specific variables
TST_DTS_URL ?= postgresql://test_user:test_pass@localhost:5/$(PROJECT_NAME)_test
TST_RDIS_URL ?= redis://localhost:/
COVRG_THRSHOLD ?= 
```

## . Best Practices

### Error Handling

```makefile
test-with-error-handling: ## Test with proper error handling
	@echo "[INFO] Running tests with error handling..."
	@if ! sega test --project . >&; then \
		echo "[ERROR] Tests failed - check test output above"; \
		echo "[INFO] Run 'make test-status' to check infrastructure"; \
		echo "[INFO] Run 'sega test local up' to restart test environment"; \
		exit 1; \
	fi
	@echo "[OK] All tests passed"
```

### Conditional Execution

```makefile
test-conditional: ## Run tests if test files exist
	@if [ -d "tests/" ] || [ -f "docker-compose.test.yml" ] || grep -q "test" package.json >/dev/null; then \
		echo "[INFO] Test infrastructure detected, running tests..."; \
		$(MAKE) test; \
	else \
		echo "[WRNING] No test infrastructure detected, skipping tests"; \
	fi
```

## . Migration Guide

### Migrating from Legacy Testing to SEGA

. **Current state**: Direct pytest/npm test calls
   ```makefile
   test:
       python -m pytest tests/
   ```

. **Migrated state**: SEGA-integrated
   ```makefile
   test: ## Run comprehensive tests via SEGA
       @sega test --project .
   ```

. **Hybrid approach** (during transition):
   ```makefile
   test: ## Run tests (SEGA preferred, fallback to legacy)
       @if command -v sega >/dev/null 2>&1; then \
           echo "[INFO] Using SEGA test orchestration..."; \
           sega test --project .; \
       else \
           echo "[INFO] SEGA not available, using legacy tests..."; \
           $(MAKE) _test-legacy; \
       fi
   ```

## . Validation and Compliance

### Makefile Validation Command

```makefile
validate-makefile: ## Validate Makefile compliance with portfolio standards
	@echo "[INFO] Validating Makefile compliance..."
	@if ! grep -q "SEGA-Integrated" Makefile; then \
		echo "[WRNING] Makefile missing SEGA integration header"; \
	fi
	@if ! make -n test >/dev/null 2>&1; then \
		echo "[ERROR] 'test' target not available"; \
		exit 1; \
	fi
	@if ! make -n help >/dev/null 2>&1; then \
		echo "[ERROR] 'help' target not available"; \
		exit 1; \
	fi
	@echo "[OK] Makefile validation passed"
```

## . Complete Example Makefile

```makefile
# Project Makefile
# Project: example Web Application  
# SEGA-Integrated Development Workflow
# 
# Standard targets: dev, dev-shared, up, test, test-unit, test-integration, 
# test-coverage, clean, help

.PHONY: help dev dev-shared up test test-unit test-integration test-e2e test-coverage test-up test-down test-status clean
.DEFAULT_GOAL := help

# Environment Variables
FLEET_ROOT ?= $(HOM)/fleet
FLEET_VENV ?= $(FLEET_ROOT)/venv
FLEET_NODE_MODULES ?= $(FLEET_ROOT)/node_modules
PROJECT_NAME ?= $(shell basename $(PWD))

## Development Workflow
dev: ## Start development environment (system Python + local npm + Docker databases)
	@echo "[INFO] Starting development environment..."
	@if [ -f "requirements.txt" ]; then pip install -r requirements.txt; fi
	@if [ -f "package.json" ]; then npm install; fi
	@$(MAKE) _start_databases
	@echo "[OK] Development environment ready"

dev-shared: ## Start development with shared dependencies
	@echo "[INFO] Starting shared development environment..."
	@if [ -f "requirements.txt" ]; then \
		source $(FLEET_VENV)/bin/activate && pip install -r requirements.txt; \
	fi
	@if [ -f "package.json" ]; then \
		ln -sf $(FLEET_NODE_MODULES) node_modules >/dev/null || \
		(npm install --prefix $(FLEET_NODE_MODULES)/.. && ln -sf $(FLEET_NODE_MODULES) node_modules); \
	fi
	@$(MAKE) _start_databases
	@echo "[OK] Shared development environment ready"

up: ## Start full Docker environment
	@echo "[INFO] Starting full Docker environment..."
	@docker-compose up -d

## SEGA-Integrated Testing Framework
test: ## Run comprehensive tests via SEGA
	@sega test --project .

test-unit: ## Run unit tests via SEGA
	@sega test --project . --suite unit

test-integration: ## Run integration tests via SEGA
	@sega test --project . --suite integration

test-coverage: ## Run tests with coverage reporting
	@sega test --project . --coverage

test-up: ## Start test infrastructure
	@sega test local up --project $(PROJECT_NAME)

test-down: ## Stop test infrastructure
	@sega test local down --project $(PROJECT_NAME)

test-status: ## Show test infrastructure status
	@sega test local status

## Utility Targets
clean: ## Clean build artifacts
	@rm -rf build/ dist/ *.egg-info/ .pytest_cache/ __pycache__/ .coverage htmlcov/
	@docker system prune -f

_start_databases: ## Internal: Start database containers
	@docker-compose up -d postgres redis >/dev/null || echo "[INFO] Some databases not available"

help: ## Show this help
	@echo "$(PROJECT_NAME) - Available Commands"
	@echo "======================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "SEGA Test Commands:"
	@echo "  sega test                  # auto-detect and run all tests"
	@echo "  sega test --coverage       # Run with coverage reporting" 
	@echo "  sega test local up         # Start test infrastructure"
```

This standardized Makefile structure ensures consistent development workflows while fully leveraging SEGA's intelligent test orchestration capabilities across all portfolio projects.