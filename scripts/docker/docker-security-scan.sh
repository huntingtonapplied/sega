#!/bin/bash

# Docker Security Scanning Script
# Scans Docker images for vulnerabilities using available tools

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "======================================"
echo "Docker Security Scanning"
echo "Date: $(date)"
echo "======================================"
echo ""

# Check for available scanning tools
SCANNER=""
if command -v trivy &> /dev/null; then
    SCANNER="trivy"
    echo -e "${GREEN}${NC} Trivy scanner found"
elif command -v grype &> /dev/null; then
    SCANNER="grype"
    echo -e "${GREEN}${NC} Grype scanner found"
elif command -v docker &> /dev/null && docker scout version &> /dev/null 2>&1; then
    SCANNER="docker-scout"
    echo -e "${GREEN}${NC} Docker Scout found"
else
    echo -e "${YELLOW}${NC} No security scanner found. Installing Trivy..."
    
    # Try to install Trivy
    if command -v apt-get &> /dev/null; then
        echo "Installing Trivy via apt..."
        curl -sfL https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
        echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee /etc/apt/sources.list.d/trivy.list
        sudo apt-get update && sudo apt-get install -y trivy
        SCANNER="trivy"
    elif command -v brew &> /dev/null; then
        echo "Installing Trivy via Homebrew..."
        brew install aquasecurity/trivy/trivy
        SCANNER="trivy"
    else
        echo -e "${RED}${NC} Could not install security scanner"
        echo "Please install Trivy, Grype, or Docker Scout manually"
        exit 1
    fi
fi

echo ""
echo "Using scanner: $SCANNER"
echo ""

# Function to scan an image
scan_image() {
    local image="$1"
    local project="$2"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}Scanning $project: $image${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    case $SCANNER in
        trivy)
            # Trivy scan with severity filtering
            trivy image --severity HIGH,CRITICAL --no-progress "$image" 2>/dev/null || {
                echo -e "${YELLOW}${NC} Could not scan $image"
                return 1
            }
            ;;
        grype)
            # Grype scan
            grype "$image" --only-fixed --fail-on high 2>/dev/null || {
                echo -e "${YELLOW}${NC} Could not scan $image"
                return 1
            }
            ;;
        docker-scout)
            # Docker Scout scan
            docker scout cves "$image" --only-severity critical,high 2>/dev/null || {
                echo -e "${YELLOW}${NC} Could not scan $image"
                return 1
            }
            ;;
    esac
    
    echo ""
}

# Function to build and scan a project
build_and_scan() {
    local project="$1"
    local dockerfile="$2"
    local context_dir=$(dirname "$dockerfile")
    
    echo "Building $project from $dockerfile..."
    
    # Build with a test tag
    if docker build -f "$dockerfile" -t "sec-scan:$project" "$context_dir" >/dev/null 2>&1; then
        echo -e "${GREEN}${NC} Build successful"
        
        # Scan the image
        scan_image "sec-scan:$project" "$project"
        
        # Clean up
        docker rmi "sec-scan:$project" >/dev/null 2>&1
    else
        echo -e "${YELLOW}${NC} Build failed for $project"
    fi
}

# Sample projects to scan
PROJECTS=(atlas hermes sega)
BASE_DIR="$HOME/workspace"

echo "Scanning sample projects..."
echo ""

for project in "${PROJECTS[@]}"; do
    PROJECT_DIR="$BASE_DIR/$project"
    
    if [ ! -d "$PROJECT_DIR" ]; then
        echo -e "${YELLOW}${NC} Project directory not found: $project"
        continue
    fi
    
    # Find main Dockerfile
    if [ -f "$PROJECT_DIR/backend/Dockerfile" ]; then
        build_and_scan "$project" "$PROJECT_DIR/backend/Dockerfile"
    elif [ -f "$PROJECT_DIR/Dockerfile" ]; then
        build_and_scan "$project" "$PROJECT_DIR/Dockerfile"
    else
        echo -e "${YELLOW}${NC} No Dockerfile found for $project"
    fi
done

# Check existing images
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Checking existing project images..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# List project-related images
PROJECT_IMAGES=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "atlas|hermes|orion|sega" 2>/dev/null || true)

if [ -n "$PROJECT_IMAGES" ]; then
    echo "Found existing project images:"
    echo "$PROJECT_IMAGES"
    echo ""

    # Scan each existing image
    while IFS= read -r image; do
        if [ "$image" != "<none>:<none>" ]; then
            scan_image "$image" "existing"
        fi
    done <<< "$PROJECT_IMAGES"
else
    echo "No existing project images found"
fi

echo ""
echo "======================================"
echo "Security Scan Complete"
echo "======================================"
echo ""
echo "Recommendations:"
echo "1. Address all CRITICAL and HIGH vulnerabilities"
echo "2. Update base images regularly"
echo "3. Use minimal base images (alpine, distroless)"
echo "4. Run security scans in CI/CD pipeline"
echo "5. Consider using image signing and verification"
echo ""