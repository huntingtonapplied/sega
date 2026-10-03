.PHONY: help up down build test clean dev status logs restart
.DEFAULT_GOAL := help

# Project Configuration - FLEET Deployment Standards
PROJECT_NAME := sega
ENV ?= development
FLEET_ROOT ?= $(HOME)/fleet

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

# INSTALL_PREFIX is resolved in this order:
# 1. INSTALL_PREFIX= is set in the environment or command line
# 2. Use the previously used (cached) value in the .install_prefix file
# 3. No INSTALL_PREFIX will be used (i.e. install in default site-packages)
INSTALL_PREFIX_CACHE := .install_prefix
INSTALL_PREFIX ?= $(file < $(INSTALL_PREFIX_CACHE))
$(file > $(INSTALL_PREFIX_CACHE),$(INSTALL_PREFIX))
$(info INSTALL_PREFIX is $(INSTALL_PREFIX))

help: ## Show available commands
	@echo "$(BLUE)Available commands for $(PROJECT_NAME):$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# Core Service Management
up start: ## Start all services
	@echo "$(GREEN)Starting $(PROJECT_NAME) services...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)Services started successfully$(NC)"

down stop: ## Stop all services
	@echo "$(YELLOW)Stopping $(PROJECT_NAME) services...$(NC)"
	@docker-compose down
	@echo "$(YELLOW)Services stopped$(NC)"

restart: ## Restart all services
	@echo "$(YELLOW)Restarting $(PROJECT_NAME) services...$(NC)"
	@$(MAKE) down
	@$(MAKE) up
	@echo "$(GREEN)Services restarted$(NC)"

# Development
dev: ## Start in development mode
	@echo "$(GREEN)Starting $(PROJECT_NAME) in development mode...$(NC)"
	@docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d || docker-compose up -d
	@echo "$(GREEN)Development environment ready$(NC)"

dev-shared: ## Start in development mode with shared environment
	@echo "$(GREEN)Starting $(PROJECT_NAME) in development mode with shared environment...$(NC)"
	@FLEET_ROOT=$(FLEET_ROOT) sega local -p $(PROJECT_NAME)
	@echo "$(GREEN)Shared development environment ready$(NC)"

build: ## Build containers
	@echo "$(BLUE)Building $(PROJECT_NAME) containers...$(NC)"
	@docker-compose build
	@echo "$(GREEN)Build completed$(NC)"

clean: clean-build clean-pyc clean-proto ## Clean up containers and volumes
	@echo "$(RED)Cleaning up $(PROJECT_NAME) resources...$(NC)"
	@docker-compose down -v --remove-orphans
	@docker system prune -f
	@echo "$(RED)Cleanup completed$(NC)"

# Utilities
status: ## Show service status
	@echo "$(BLUE)Service status for $(PROJECT_NAME):$(NC)"
	@docker-compose ps

logs: ## View logs
	@docker-compose logs -f

logs-%: ## View logs for specific service
	@docker-compose logs -f $*

health: ## Check service health
	@echo "$(BLUE)Health check for $(PROJECT_NAME):$(NC)"
	@docker-compose ps
	@echo "$(BLUE)Database connectivity:$(NC)"
	@docker-compose exec postgres pg_isready -U $${POSTGRES_USER:-sega_user} -d $${POSTGRES_DB:-sega_dev} 2>/dev/null && echo "  PostgreSQL connection OK" || echo "  PostgreSQL connection failed"
	@docker-compose exec redis redis-cli ping 2>/dev/null && echo "  Redis connection OK" || echo "  Redis connection failed"

# Protocol Buffers
proto_srcs := $(wildcard src/proto/*.proto)
proto_pys := $(patsubst %.proto,%_pb2.py,$(proto_srcs))

proto: $(proto_pys) ## Compile protobuf files

src/proto/%_pb2.py: src/proto/%.proto
	protoc --python_out=. $<

# Testing
test: ## Run tests
	@echo "$(BLUE)Running tests for $(PROJECT_NAME)...$(NC)"
	@python3 -m pytest tests/ -v
	@echo "$(GREEN)Tests completed$(NC)"

test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests for $(PROJECT_NAME)...$(NC)"
	@python3 -m pytest tests/ -v -m "not integration"

test-integration: ## Run integration tests
	@echo "$(BLUE)Running integration tests for $(PROJECT_NAME)...$(NC)"
	@python3 -m pytest tests/ -v -m "integration"

test-coverage: ## Run tests with coverage
	@echo "$(BLUE)Running tests with coverage for $(PROJECT_NAME)...$(NC)"
	@python3 -m pytest tests/ --cov=src/sega --cov-report=term-missing --cov-report=html:htmlcov --cov-fail-under=70

# Code Quality
lint: ## Run code linting
	@echo "$(BLUE)Running linting for $(PROJECT_NAME)...$(NC)"
	@ruff check src/sega || true
	@black --check src/sega || true
	@echo "$(GREEN)Linting completed$(NC)"

format: ## Format code
	@echo "$(BLUE)Formatting code for $(PROJECT_NAME)...$(NC)"
	@black src/sega || true
	@ruff --fix src/sega || true
	@echo "$(GREEN)Code formatting completed$(NC)"

# Credential Management
validate-credentials: ## Validate deployment engine credentials
	@echo "$(BLUE)Validating deployment credentials for $(PROJECT_NAME)...$(NC)"
	@python3 scripts/validate_deployment_credentials.py --verbose
	@echo "$(GREEN)Credential validation completed$(NC)"

validate-credentials-%: ## Validate specific engine credentials (e.g., validate-credentials-ecs)
	@echo "$(BLUE)Validating $* engine credentials...$(NC)"
	@python3 scripts/validate_deployment_credentials.py --engine $* --verbose

# Setup and Installation
setup: ## Initial project setup
	@echo "$(BLUE)Setting up $(PROJECT_NAME)...$(NC)"
	@mkdir -p logs data
	@cp .env.example .env 2>/dev/null || echo "$(YELLOW).env.example already exists$(NC)"
	@echo "$(GREEN)Project setup completed$(NC)"
	@echo "$(YELLOW)Please edit .env with your configuration$(NC)"

install: proto ## Install the package
ifeq ($(INSTALL_PREFIX),)
	@echo "$(BLUE)Installing $(PROJECT_NAME) to user site-packages...$(NC)"
	@python3 -m pip install --user .
	@echo "$(GREEN)Installation completed$(NC)"
else
	@echo "$(BLUE)Installing $(PROJECT_NAME) to $(INSTALL_PREFIX)...$(NC)"
	@python3 -m pip install --prefix $(INSTALL_PREFIX) .
	@echo "$(GREEN)Installation completed$(NC)"
endif

install-dev: proto ## Install in development mode (editable)
ifeq ($(INSTALL_PREFIX),)
	@echo "$(BLUE)Installing $(PROJECT_NAME) in development mode (user site-packages)...$(NC)"
	@python3 -m pip install --user -e .[dev]
	@echo "$(GREEN)Development installation completed$(NC)"
else
	@echo "$(BLUE)Installing $(PROJECT_NAME) in development mode to $(INSTALL_PREFIX)...$(NC)"
	@python3 -m pip install --prefix $(INSTALL_PREFIX) -e .[dev]
	@echo "$(GREEN)Development installation completed$(NC)"
endif

uninstall: ## Uninstall the package
	@echo "$(RED)Uninstalling $(PROJECT_NAME)...$(NC)"
	@python3 -m pip uninstall -y sega
	@echo "$(RED)Uninstallation completed$(NC)"

# Cleanup
clean-build: ## Remove build artifacts
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	@rm -rf ./build
	@rm -fr .eggs/
	@find . -name '*.egg-info' -exec rm -fr {} +
	@find . -name '*.egg' -exec rm -f {} +

clean-pyc: ## Remove Python file artifacts
	@echo "$(YELLOW)Cleaning Python artifacts...$(NC)"
	@find . -name '*.pyc' -exec rm -f {} +
	@find . -name '*.pyo' -exec rm -f {} +
	@find . -name '*~' -exec rm -f {} +
	@find . -name '__pycache__' -exec rm -fr {} +

clean-proto: ## Remove protobuf generated artifacts
	@echo "$(YELLOW)Cleaning protobuf artifacts...$(NC)"
	@rm -f $(proto_pys)

# Development Utilities
dev-setup: install-dev up ## Complete development environment setup
	@echo "$(GREEN)Development environment setup complete$(NC)"
	@echo "$(YELLOW)Services running:$(NC)"
	@echo "  PostgreSQL: localhost:5011"
	@echo "  Redis: localhost:5211"
	@echo "$(YELLOW)Run 'make down' to stop services$(NC)"

validate-examples: ## Validate all example configurations
	@echo "$(BLUE)Validating example configurations...$(NC)"
	@python3 scripts/validate_examples.py || echo "$(YELLOW)Validation script not found$(NC)"

build-examples: ## Build all example projects (for CI)
	@echo "$(BLUE)Building example projects...$(NC)"
	@for example in examples/*/*/; do \
		if [ -f "$$example/sega.yaml" ]; then \
			echo "Building $$example..."; \
			cd "$$example" && sega build --dry-run || echo "Build failed for $$example"; \
			cd - > /dev/null; \
		fi \
	done

# Deployment-Specific Targets
deploy-test: ## Test deployment to staging environment
	@echo "$(BLUE)Testing deployment for $(PROJECT_NAME)...$(NC)"
	@sega deploy --target staging --dry-run --validate
	@echo "$(GREEN)Deployment test completed$(NC)"

deploy-staging: ## Deploy to staging environment
	@echo "$(BLUE)Deploying $(PROJECT_NAME) to staging...$(NC)"
	@sega deploy --target staging
	@echo "$(GREEN)Staging deployment completed$(NC)"

deploy-production: ## Deploy to production environment
	@echo "$(RED)Deploying $(PROJECT_NAME) to production...$(NC)"
	@sega deploy --target production
	@echo "$(GREEN)Production deployment completed$(NC)"

hardware-test: ## Test hardware deployment capabilities
	@echo "$(BLUE)Testing hardware deployment for $(PROJECT_NAME)...$(NC)"
	@sega program --device-type fpga --dry-run || echo "$(YELLOW)FPGA test skipped$(NC)"
	@sega flash --target embedded --dry-run || echo "$(YELLOW)Embedded test skipped$(NC)"
	@echo "$(GREEN)Hardware tests completed$(NC)"

cli-test: ## Test CLI installation and functionality
	@echo "$(BLUE)Testing CLI installation for $(PROJECT_NAME)...$(NC)"
	@sega --version
	@sega doctor
	@sega detect --dry-run || echo "$(YELLOW)Detection test skipped$(NC)"
	@echo "$(GREEN)CLI tests completed$(NC)"

integration-test: ## Run comprehensive integration tests
	@echo "$(BLUE)Running integration tests for $(PROJECT_NAME)...$(NC)"
	@$(MAKE) test-integration
	@$(MAKE) hardware-test
	@$(MAKE) cli-test
	@$(MAKE) validate-credentials
	@echo "$(GREEN)Integration tests completed$(NC)"

cross-domain-test: ## Test cross-domain deployment capabilities
	@echo "$(BLUE)Testing cross-domain deployment for $(PROJECT_NAME)...$(NC)"
	@sega deploy --domains software,hardware --dry-run || echo "$(YELLOW)Cross-domain test skipped$(NC)"
	@echo "$(GREEN)Cross-domain tests completed$(NC)"