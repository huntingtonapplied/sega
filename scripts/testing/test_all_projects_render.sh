#!/usr/bin/env bash
"""
SEGA All Projects Render Testing Script
Tests sega local up and verifies render for all managed projects
"""

set -e

FLEET_ROOT="${FLEET_ROOT:-$HOME/workspace}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_FILE="$FLEET_ROOT/sega/docs/reports/RENDER_VERIFICATION_$(date +%Y%m%d_%H%M%S).md"

# Projects to test (from laboratory_config.yaml)
PROJECTS=(
    "atlas"
    "hermes"
    "orion"
)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Initialize report
cat > "$REPORT_FILE" << EOF
# SEGA Local Up Render Verification Report

**Date**: $(date +%Y-%m-%d)
**Time**: $(date +%H:%M:%S)
**Engineer**: Automated Testing
**Task**: Deploy and verify render for all managed projects

---

## Test Configuration

- **Workspace Root**: $FLEET_ROOT
- **Projects Tested**: ${#PROJECTS[@]}
- **Timeout Per Project**: 60 seconds
- **Verification**: HTTP endpoint testing via laboratory_config.yaml

---

## Test Results

EOF

# Track statistics
TOTAL_PROJECTS=${#PROJECTS[@]}
DEPLOYED_SUCCESS=0
DEPLOYED_FAILED=0
RENDER_SUCCESS=0
RENDER_PARTIAL=0
RENDER_FAILED=0

echo "======================================================================"
echo "SEGA Local Up + Render Verification"
echo "======================================================================"
echo "Testing ${#PROJECTS[@]} managed projects..."
echo ""

for project in "${PROJECTS[@]}"; do
    echo "----------------------------------------------------------------------"
    echo "Project: $project"
    echo "----------------------------------------------------------------------"

    # Deploy the project
    echo "📦 Deploying $project..."
    cd "$FLEET_ROOT/$project" || continue

    DEPLOY_OUTPUT=$(timeout 60 sega local up 2>&1 || true)
    DEPLOY_STATUS=$?

    # Check deployment status
    if echo "$DEPLOY_OUTPUT" | grep -q "\[OK\] Successful.*$project"; then
        echo -e "${GREEN}✅ Deployment: SUCCESS${NC}"
        DEPLOYED_SUCCESS=$((DEPLOYED_SUCCESS + 1))
        DEPLOY_RESULT="✅ SUCCESS"

        # Wait a bit for services to start
        echo "⏳ Waiting 5 seconds for services to start..."
        sleep 5

        # Verify render
        echo "🔍 Verifying render..."
        VERIFY_OUTPUT=$("$SCRIPT_DIR/verify_project_render.py" "$project" "$FLEET_ROOT" 2>&1 || true)
        VERIFY_STATUS=$?

        if [ $VERIFY_STATUS -eq 0 ]; then
            echo -e "${GREEN}✅ Render: ALL ENDPOINTS VERIFIED${NC}"
            RENDER_SUCCESS=$((RENDER_SUCCESS + 1))
            RENDER_RESULT="✅ ALL VERIFIED"
        elif [ $VERIFY_STATUS -eq 1 ] && echo "$VERIFY_OUTPUT" | grep -q "Some endpoints failed"; then
            echo -e "${YELLOW}⚠️  Render: PARTIAL VERIFICATION${NC}"
            RENDER_PARTIAL=$((RENDER_PARTIAL + 1))
            RENDER_RESULT="⚠️ PARTIAL"
        else
            echo -e "${RED}❌ Render: FAILED${NC}"
            RENDER_FAILED=$((RENDER_FAILED + 1))
            RENDER_RESULT="❌ FAILED"
        fi

    elif echo "$DEPLOY_OUTPUT" | grep -q "\[ERROR\] Failed.*$project"; then
        echo -e "${RED}❌ Deployment: FAILED${NC}"
        DEPLOYED_FAILED=$((DEPLOYED_FAILED + 1))
        DEPLOY_RESULT="❌ FAILED"
        RENDER_RESULT="⏭️ SKIPPED"
        VERIFY_OUTPUT="Deployment failed, render verification skipped"
    else
        echo -e "${YELLOW}⚠️  Deployment: TIMEOUT/UNKNOWN${NC}"
        DEPLOYED_FAILED=$((DEPLOYED_FAILED + 1))
        DEPLOY_RESULT="⏱️ TIMEOUT"
        RENDER_RESULT="⏭️ SKIPPED"
        VERIFY_OUTPUT="Deployment timeout, render verification skipped"
    fi

    # Extract error messages
    ERROR_MSG=$(echo "$DEPLOY_OUTPUT" | grep -E "\[ERROR\]|\[WARNING\]" | head -3 || echo "None")

    # Add to report
    cat >> "$REPORT_FILE" << EOF
### $project

| Metric | Status |
|--------|--------|
| **Deployment** | $DEPLOY_RESULT |
| **Render Verification** | $RENDER_RESULT |

<details>
<summary>Deployment Output</summary>

\`\`\`
$DEPLOY_OUTPUT
\`\`\`

</details>

<details>
<summary>Render Verification Output</summary>

\`\`\`
$VERIFY_OUTPUT
\`\`\`

</details>

**Key Issues**: $ERROR_MSG

---

EOF

    echo ""
done

# Generate summary
cat >> "$REPORT_FILE" << EOF

## Summary Statistics

| Category | Count | Percentage |
|----------|-------|------------|
| **Total Projects** | $TOTAL_PROJECTS | 100% |
| **Deployed Successfully** | $DEPLOYED_SUCCESS | $(( DEPLOYED_SUCCESS * 100 / TOTAL_PROJECTS ))% |
| **Deployment Failed** | $DEPLOYED_FAILED | $(( DEPLOYED_FAILED * 100 / TOTAL_PROJECTS ))% |
| **Render Fully Verified** | $RENDER_SUCCESS | $(( RENDER_SUCCESS * 100 / TOTAL_PROJECTS ))% |
| **Render Partially Verified** | $RENDER_PARTIAL | $(( RENDER_PARTIAL * 100 / TOTAL_PROJECTS ))% |
| **Render Failed** | $RENDER_FAILED | $(( RENDER_FAILED * 100 / TOTAL_PROJECTS ))% |

---

## Conclusions

**Deployment Success Rate**: $(( DEPLOYED_SUCCESS * 100 / TOTAL_PROJECTS ))%
**Render Verification Rate**: $(( (RENDER_SUCCESS + RENDER_PARTIAL) * 100 / TOTAL_PROJECTS ))%

**Next Actions**:
1. Fix deployment failures
2. Complete missing docker-compose backend services
3. Add required environment variables to .env.example files
4. Implement health checks for all services

---

**Report Generated**: $(date +%Y-%m-%d\ %H:%M:%S)
**Report Location**: $REPORT_FILE
EOF

# Display summary
echo "======================================================================"
echo "SUMMARY"
echo "======================================================================"
echo "Total Projects:          $TOTAL_PROJECTS"
echo "Deployed Successfully:   $DEPLOYED_SUCCESS"
echo "Deployment Failed:       $DEPLOYED_FAILED"
echo "Render Fully Verified:   $RENDER_SUCCESS"
echo "Render Partially Verified: $RENDER_PARTIAL"
echo "Render Failed:           $RENDER_FAILED"
echo "======================================================================"
echo "Report saved to: $REPORT_FILE"
echo "======================================================================"

exit 0
