#!/bin/bash

# Docker Security Validation Script
# Validates Docker configurations meet security standards

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECTS=(atlas hermes orion sega)
BASE_DIR="$HOME/workspace"
REPORT_FILE="docker_validation_report_$(date +%Y%m%d_%H%M%S).txt"

# UID Range check
MIN_UID=10001
MAX_UID=19999

echo "======================================"
echo "Docker Security Validation"
echo "Date: $(date)"
echo "======================================"
echo ""

# Initialize counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNINGS=0

# Function to check result
check_result() {
    local check_name="$1"
    local result="$2"
    local expected="$3"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    if [ "$result" = "$expected" ]; then
        echo -e "${GREEN}${NC} $check_name"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "${RED}${NC} $check_name (got: $result, expected: $expected)"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

# Function to check warning
check_warning() {
    local check_name="$1"
    local result="$2"
    
    if [ -n "$result" ]; then
        echo -e "${YELLOW}${NC} $check_name: $result"
        WARNINGS=$((WARNINGS + 1))
    fi
}

# Function to validate Dockerfile
validate_dockerfile() {
    local project="$1"
    local dockerfile="$2"
    
    echo "  Checking $dockerfile..."
    
    if [ ! -f "$dockerfile" ]; then
        echo "    File not found"
        return 1
    fi
    
    # Check for USER instruction
    if grep -q "^USER " "$dockerfile"; then
        local user=$(grep "^USER " "$dockerfile" | tail -1 | awk '{print $2}')
        if [ "$user" != "root" ]; then
            echo -e "    ${GREEN}${NC} Non-root user: $user"
        else
            echo -e "    ${RED}${NC} Running as root"
            return 1
        fi
    else
        echo -e "    ${YELLOW}${NC} No USER instruction found"
    fi
    
    # Check for HEALTHCHECK
    if grep -q "^HEALTHCHECK" "$dockerfile"; then
        echo -e "    ${GREEN}${NC} Health check present"
    else
        echo -e "    ${YELLOW}${NC} No health check"
    fi
    
    # Check for UID in range
    if grep -q "APP_UID\|UID" "$dockerfile"; then
        local uid=$(grep -E "APP_UID|UID" "$dockerfile" | grep -oE "[0-9]{5}" | head -1)
        if [ -n "$uid" ]; then
            if [ "$uid" -ge "$MIN_UID" ] && [ "$uid" -le "$MAX_UID" ]; then
                echo -e "    ${GREEN}${NC} UID in range: $uid"
            else
                echo -e "    ${RED}${NC} UID out of range: $uid"
            fi
        fi
    fi
    
    # Check for security best practices
    if grep -q "apk add --no-cache\|apt-get.*clean" "$dockerfile"; then
        echo -e "    ${GREEN}${NC} Package cache cleaned"
    fi
    
    return 0
}

# Function to validate docker-compose
validate_docker_compose() {
    local project="$1"
    local compose_file="$2"
    
    echo "  Checking $compose_file..."
    
    if [ ! -f "$compose_file" ]; then
        echo "    File not found"
        return 1
    fi
    
    # Check for user mapping
    if grep -q "user:" "$compose_file"; then
        echo -e "    ${GREEN}${NC} User mapping present"
    else
        echo -e "    ${YELLOW}${NC} No user mapping"
    fi
    
    # Check for security options
    if grep -q "security_opt:" "$compose_file"; then
        echo -e "    ${GREEN}${NC} Security options present"
        if grep -q "no-new-privileges" "$compose_file"; then
            echo -e "    ${GREEN}${NC} Privilege escalation prevented"
        fi
    else
        echo -e "    ${YELLOW}${NC} No security options"
    fi
    
    # Check for read_only
    if grep -q "read_only: true" "$compose_file"; then
        echo -e "    ${GREEN}${NC} Read-only filesystem"
    fi
    
    # Check for tmpfs
    if grep -q "tmpfs:" "$compose_file"; then
        echo -e "    ${GREEN}${NC} tmpfs mounts present"
    fi
    
    # Check for dangerous mounts
    if grep -q "/var/run/docker.sock" "$compose_file"; then
        echo -e "    ${RED}${NC} Docker socket mounted (security risk)"
    fi
    
    return 0
}

# Function to test container build
test_container_build() {
    local project="$1"
    local dockerfile="$2"
    
    echo "  Testing build..."
    
    # Try to build with a test tag
    if docker build -f "$dockerfile" -t "sec-test:$project" . >/dev/null 2>&1; then
        echo -e "    ${GREEN}${NC} Build successful"
        
        # Check image for user
        local user=$(docker run --rm "sec-test:$project" whoami 2>/dev/null || echo "root")
        if [ "$user" != "root" ]; then
            echo -e "    ${GREEN}${NC} Container runs as: $user"
        else
            echo -e "    ${YELLOW}${NC} Container runs as root"
        fi
        
        # Clean up test image
        docker rmi "sec-test:$project" >/dev/null 2>&1
        
        return 0
    else
        echo -e "    ${YELLOW}${NC} Build failed (may need dependencies)"
        return 1
    fi
}

# Main validation loop
echo "Starting validation of ${#PROJECTS[@]} projects..."
echo ""

for project in "${PROJECTS[@]}"; do
    PROJECT_DIR="$BASE_DIR/$project"
    
    if [ ! -d "$PROJECT_DIR" ]; then
        echo -e "${YELLOW}${NC} Project directory not found: $project"
        continue
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Project: $project"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Find Dockerfiles
    DOCKERFILES=$(find "$PROJECT_DIR" -name "Dockerfile*" -type f 2>/dev/null | head -5)
    
    if [ -z "$DOCKERFILES" ]; then
        echo -e "${YELLOW}${NC} No Dockerfiles found"
    else
        for dockerfile in $DOCKERFILES; do
            validate_dockerfile "$project" "$dockerfile"
        done
    fi
    
    # Find docker-compose files
    COMPOSE_FILES=$(find "$PROJECT_DIR" -name "docker-compose*.yml" -type f 2>/dev/null | head -5)
    
    if [ -n "$COMPOSE_FILES" ]; then
        for compose in $COMPOSE_FILES; do
            validate_docker_compose "$project" "$compose"
        done
    fi
    
    # Check .env.example
    ENV_FILE="$PROJECT_DIR/.env.example"
    if [ -f "$ENV_FILE" ]; then
        echo "  Checking .env.example..."
        if grep -q "APP_UID\|APP_GID" "$ENV_FILE"; then
            echo -e "    ${GREEN}${NC} UID/GID variables present"
        else
            echo -e "    ${YELLOW}${NC} No UID/GID variables"
        fi
    fi
    
    echo ""
done

# Summary
echo "======================================"
echo "Validation Summary"
echo "======================================"
echo "Total checks: $TOTAL_CHECKS"
echo -e "${GREEN}Passed: $PASSED_CHECKS${NC}"
echo -e "${RED}Failed: $FAILED_CHECKS${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
echo ""

# Compliance calculation
if [ $FAILED_CHECKS -eq 0 ]; then
    echo -e "${GREEN} COMPLIANT: All critical security checks passed${NC}"
    exit 0
else
    echo -e "${RED} NON-COMPLIANT: Critical security issues found${NC}"
    exit 1
fi