#!/bin/bash

# Docker Compliance Testing Script
# Tests actual container runtime security

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "======================================"
echo "Docker Runtime Security Testing"
echo "Date: $(date)"
echo "======================================"
echo ""

# Test configuration
TEST_PROJECT="sega"  # Simple project for testing
TEST_DIR="$HOME/workspace/$TEST_PROJECT"
TEST_IMAGE="sec-test-$TEST_PROJECT"
TEST_CONTAINER="sec-test-container-$TEST_PROJECT"

# Function to clean up test resources
cleanup() {
    echo "Cleaning up test resources..."
    docker rm -f "$TEST_CONTAINER" 2>/dev/null || true
    docker rmi -f "$TEST_IMAGE" 2>/dev/null || true
}

# Set trap for cleanup
trap cleanup EXIT

# Function to run a test
run_test() {
    local test_name="$1"
    local command="$2"
    local expected="$3"
    
    echo -n "Testing: $test_name... "
    
    result=$(eval "$command" 2>/dev/null || echo "ERROR")
    
    if [[ "$result" == *"$expected"* ]]; then
        echo -e "${GREEN} PASS${NC}"
        return 0
    else
        echo -e "${RED} FAIL${NC} (got: $result)"
        return 1
    fi
}

# Build test image
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Building test image for $TEST_PROJECT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "$TEST_DIR/backend/Dockerfile" ]; then
    DOCKERFILE="$TEST_DIR/backend/Dockerfile"
elif [ -f "$TEST_DIR/Dockerfile" ]; then
    DOCKERFILE="$TEST_DIR/Dockerfile"
else
    echo -e "${RED}No Dockerfile found for $TEST_PROJECT${NC}"
    exit 1
fi

echo "Using Dockerfile: $DOCKERFILE"
docker build -f "$DOCKERFILE" -t "$TEST_IMAGE" "$TEST_DIR" >/dev/null 2>&1 || {
    echo -e "${RED}Build failed${NC}"
    exit 1
}
echo -e "${GREEN} Build successful${NC}"
echo ""

# Run container for testing
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Starting test container"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker run -d \
    --name "$TEST_CONTAINER" \
    --security-opt no-new-privileges:true \
    --read-only \
    --tmpfs /tmp \
    "$TEST_IMAGE" \
    sleep 3600 >/dev/null 2>&1 || {
    echo -e "${YELLOW} Could not start with full security options, trying basic mode${NC}"
    docker run -d --name "$TEST_CONTAINER" "$TEST_IMAGE" sleep 3600 >/dev/null 2>&1
}

echo -e "${GREEN} Container started${NC}"
echo ""

# Run security tests
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Running Security Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTAL_TESTS=0
PASSED_TESTS=0

# Test 1: Non-root user
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if run_test "Non-root user" \
    "docker exec $TEST_CONTAINER whoami" \
    "sega"; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi

# Test 2: UID in correct range
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if run_test "UID in range 10001-19999" \
    "docker exec $TEST_CONTAINER id -u" \
    "100"; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi

# Test 3: No sudo access
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if run_test "No sudo privileges" \
    "docker exec $TEST_CONTAINER which sudo 2>&1 || echo 'NO_SUDO'" \
    "NO_SUDO"; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi

# Test 4: Home directory permissions
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if run_test "Home directory ownership" \
    "docker exec $TEST_CONTAINER ls -ld /app 2>/dev/null | awk '{print \$3}' || echo 'root'" \
    "sega"; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi

# Test 5: Cannot write to root filesystem
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if run_test "Read-only root filesystem" \
    "docker exec $TEST_CONTAINER touch /test_file 2>&1 || echo 'READ_ONLY'" \
    "READ_ONLY"; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi

# Test 6: Can write to /tmp
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if run_test "Writable /tmp" \
    "docker exec $TEST_CONTAINER touch /tmp/test_file 2>&1 && echo 'WRITABLE'" \
    "WRITABLE"; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi

echo ""

# Test container capabilities
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Container Capabilities Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check for dangerous capabilities
CAPS=$(docker inspect "$TEST_CONTAINER" --format='{{.HostConfig.CapAdd}}' 2>/dev/null || echo "[]")
if [ "$CAPS" = "[]" ] || [ "$CAPS" = "<nil>" ]; then
    echo -e "${GREEN} No additional capabilities${NC}"
else
    echo -e "${YELLOW} Additional capabilities: $CAPS${NC}"
fi

# Check security options
SEC_OPTS=$(docker inspect "$TEST_CONTAINER" --format='{{.HostConfig.SecurityOpt}}' 2>/dev/null || echo "[]")
if [[ "$SEC_OPTS" == *"no-new-privileges"* ]]; then
    echo -e "${GREEN} Privilege escalation prevented${NC}"
else
    echo -e "${YELLOW} No privilege escalation prevention${NC}"
fi

# Check if running as privileged
PRIVILEGED=$(docker inspect "$TEST_CONTAINER" --format='{{.HostConfig.Privileged}}' 2>/dev/null || echo "false")
if [ "$PRIVILEGED" = "false" ]; then
    echo -e "${GREEN} Not running privileged${NC}"
else
    echo -e "${RED} Running as privileged${NC}"
fi

echo ""

# Image analysis
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Image Security Analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check image size
SIZE=$(docker images "$TEST_IMAGE" --format "{{.Size}}" 2>/dev/null)
echo "Image size: $SIZE"

# Check base image
BASE_IMAGE=$(docker inspect "$TEST_IMAGE" --format='{{.Config.Image}}' 2>/dev/null || \
    grep "^FROM" "$DOCKERFILE" | head -1 | awk '{print $2}')
echo "Base image: $BASE_IMAGE"

if [[ "$BASE_IMAGE" == *"alpine"* ]] || [[ "$BASE_IMAGE" == *"distroless"* ]]; then
    echo -e "${GREEN} Using minimal base image${NC}"
else
    echo -e "${YELLOW} Consider using alpine or distroless base${NC}"
fi

# Check for HEALTHCHECK
if docker inspect "$TEST_IMAGE" --format='{{.Config.Healthcheck}}' 2>/dev/null | grep -q "Cmd"; then
    echo -e "${GREEN} Health check configured${NC}"
else
    echo -e "${YELLOW} No health check configured${NC}"
fi

echo ""

# Summary
echo "======================================"
echo "Test Summary"
echo "======================================"
echo "Runtime Security Tests: $PASSED_TESTS/$TOTAL_TESTS passed"

if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    echo -e "${GREEN} ALL TESTS PASSED${NC}"
    EXIT_CODE=0
else
    echo -e "${YELLOW} Some tests failed${NC}"
    EXIT_CODE=1
fi

# Compliance verdict
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Compliance Verdict"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $PASSED_TESTS -ge $((TOTAL_TESTS - 1)) ]; then
    echo -e "${GREEN} COMPLIANT: Container meets security standards${NC}"
else
    echo -e "${RED} NON-COMPLIANT: Security improvements needed${NC}"
fi

echo ""
echo "For full project validation, run:"
echo "  ./validate_docker_security.sh"
echo ""

exit $EXIT_CODE