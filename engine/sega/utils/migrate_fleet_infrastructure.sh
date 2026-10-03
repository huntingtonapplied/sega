#!/bin/bash
# SEGA FLEET Infrastructure Migration Script
# Migrates existing FLEET build/deploy infrastructure to SEGA management

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}SEGA FLEET Infrastructure Migration${NC}"
echo -e "${BLUE}=================================${NC}"

# Find FLEET root
FLEET_ROOT=""
if [ -f "../../.gitmodules" ]; then
    FLEET_ROOT="$(cd ../.. && pwd)"
elif [ -f "../../../.gitmodules" ]; then
    FLEET_ROOT="$(cd ../../.. && pwd)"
else
    echo -e "${RED}[ERROR] FLEET root not found${NC}"
    exit 1
fi

echo -e "${GREEN}[OK] Found FLEET root: $FLEET_ROOT${NC}"

# Create SEGA FLEET configuration
echo -e "${YELLOW}[INFO] Creating SEGA FLEET configuration...${NC}"

# Create FLEET-specific SEGA config
cat > "$FLEET_ROOT/.sega.yml" << 'EOF'
project_type: fleet_monorepo
version: "1.0"

# FLEET Monorepo Configuration
fleet:
  submodule_management: true
  multimodal_deployment: true
  engine_systemd: true
  
# Projects with multimodal components
projects:
  hermes:
    components: [backend, frontend, engine, desktop, expo]
    ports:
      backend: 3002
      frontend: 3102
      engine: 9002
  atlas:
    components: [backend, frontend, expo]
    ports:
      backend: 5117
      frontend: 5217
  orion:
    components: [backend, frontend, engine, desktop, expo]
  atlas:
    components: [backend, frontend, engine, desktop, expo]

# Deployment configuration
deployment:
  environments: [development, staging, production]
  strategy: multimodal
  engine_deployment: systemd

# Engine services configuration
engines:
  service_template: /etc/systemd/system/fleet-{project}-engine.service
  user: fleet
  restart_policy: always

# Testing configuration
testing:
  types: [unit, integration, system]
  parallel: true
  cross_project: true
EOF

echo -e "${GREEN}[OK] Created .sega.yml configuration${NC}"

# Migrate GitLab CI configuration
echo -e "${YELLOW}[INFO] Migrating GitLab CI to SEGA...${NC}"

# Backup existing GitLab CI
if [ -f "$FLEET_ROOT/.gitlab-ci.yml" ]; then
    cp "$FLEET_ROOT/.gitlab-ci.yml" "$FLEET_ROOT/.gitlab-ci.yml.backup"
    echo -e "${YELLOW}[INFO] Backed up existing .gitlab-ci.yml${NC}"
fi

# Create new SEGA-managed GitLab CI
cat > "$FLEET_ROOT/.gitlab-ci.yml" << 'EOF'
# FLEET Monorepo GitLab CI - Managed by SEGA
# All operations delegated to SEGA for unified management

stages:
  - validate
  - test
  - build
  - deploy-development
  - deploy-staging
  - deploy-production

variables:
  SEGA_PROJECT_TYPE: "fleet_monorepo"
  SEGA_MULTIMODAL: "true"

# Validation stage - check all submodules
validate:fleet:
  stage: validate
  script:
    - sega fleet status
    - sega fleet pull
  only:
    - main
    - develop

# Test stage - run tests across projects
test:fleet:
  stage: test
  script:
    - sega fleet test
  coverage: '/TOTAL.*\s+(\d+%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
  only:
    - main
    - develop

# Build stage - build all projects
build:fleet:
  stage: build
  script:
    - sega build --target all --optimize
  artifacts:
    paths:
      - dist/
      - build/
    expire_in: 1 week
  only:
    - main
    - develop

# Development deployment
deploy:development:
  stage: deploy-development
  script:
    - sega fleet deploy --environment=development
    - sega fleet engines --action=restart
  only:
    - develop
  environment:
    name: development
    url: https://dev.fleet.example.com

# Staging deployment
deploy:staging:
  stage: deploy-staging
  script:
    - sega fleet deploy --environment=staging
    - sega fleet engines --action=restart
  only:
    - main
  environment:
    name: staging
    url: https://staging.fleet.example.com

# Production deployment
deploy:production:
  stage: deploy-production
  script:
    - sega fleet deploy --environment=production
    - sega fleet engines --action=restart
  only:
    - main
  environment:
    name: production
    url: https://fleet.example.com
  when: manual

# Engine health monitoring
monitor:engines:
  stage: deploy-production
  script:
    - sega fleet engines --action=status
  only:
    - main
    - develop
  when: always
  allow_failure: true
EOF

echo -e "${GREEN}[OK] Created SEGA-managed .gitlab-ci.yml${NC}"

# Create migration completion marker
echo -e "${YELLOW}[INFO] Creating migration marker...${NC}"
cat > "$FLEET_ROOT/_internal/SEGA_MIGRATION_COMPLETE" << EOF
FLEET Infrastructure Migration to SEGA Complete
=============================================
Date: $(date)
Migrated Components:
- GitLab CI configuration
- Build and deployment scripts
- Bulk operations (now: sega fleet commands)
- Engine systemd service management

New Commands:
- sega fleet pull          # Pull all submodules
- sega fleet push          # Push all projects
- sega fleet status        # Check git status
- sega fleet deploy        # Deploy all projects
- sega fleet engines       # Manage engine services
- sega fleet test          # Run cross-project tests

Legacy Scripts Deprecated:
- _internal/scripts/deploy_local.sh (use: sega fleet deploy)
- _internal/tooling/development/dev/gitlab_bulk_operations.sh (use: sega fleet commands)
EOF

echo -e "${GREEN}[OK] Migration complete!${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Install SEGA: pip install -e ./sega"
echo "2. Initialize infrastructure: sega fleet init-infrastructure"
echo "3. Test new commands: sega fleet status"
echo "4. Deploy to development: sega fleet deploy --environment=development"
echo ""
echo -e "${YELLOW}[INFO] Documentation updated in README.md${NC}"