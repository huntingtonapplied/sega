#!/bin/bash
# =============================================================================
# Full Testing Pipeline
# =============================================================================
# Runs complete testing sequence: Health Check → API Testing → Browser Tests
#
# Usage: ./full-test-pipeline.sh [OPTIONS]
#   -i, --instance <1|2>   Instance number (default: 2)
#   -p, --project <name>   Test specific project only
#   -s, --skip-browser     Skip browser tests
#   -q, --quick            Quick mode (health + API health only)
#   -h, --help             Show this help
#
# Pipeline Phases:
#   Phase 1: Health Check (ports, docker, nginx, service health)
#   Phase 2: API Testing (endpoint validation, CRUD chains)
#   Phase 3: Browser Testing (e2e, visual, a11y, performance)
#
# =============================================================================

set -e

# Configuration
INSTANCE=2
PROJECT=""
SKIP_BROWSER=false
QUICK_MODE=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Instance configurations
# Set SYSMON_INSTANCE<N>_IP, or configure [instances] in config/sega.toml
# (injected via the sega CLI).
declare -A INSTANCE_IPS=(
    [1]="${SYSMON_INSTANCE1_IP:-}"
    [2]="${SYSMON_INSTANCE2_IP:-}"
)

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--instance)
            INSTANCE="$2"
            shift 2
            ;;
        -p|--project)
            PROJECT="$2"
            shift 2
            ;;
        -s|--skip-browser)
            SKIP_BROWSER=true
            shift
            ;;
        -q|--quick)
            QUICK_MODE=true
            shift
            ;;
        -h|--help)
            echo "Full Testing Pipeline"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -i, --instance <1|2>   Instance number (default: 2)"
            echo "  -p, --project <name>   Test specific project only"
            echo "  -s, --skip-browser     Skip browser tests"
            echo "  -q, --quick            Quick mode (health + API health only)"
            echo "  -h, --help             Show this help"
            echo ""
            echo "Pipeline Phases:"
            echo "  Phase 1: Health Check (ports, docker, nginx, service health)"
            echo "  Phase 2: API Testing (endpoint validation, CRUD chains)"
            echo "  Phase 3: Browser Testing (e2e, visual, a11y, performance)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate instance
if [[ ! "${INSTANCE_IPS[$INSTANCE]+exists}" ]]; then
    echo "Error: Invalid instance number. Use 1 or 2."
    exit 1
fi

IP="${INSTANCE_IPS[$INSTANCE]}"

if [[ -z "$IP" ]]; then
    echo "Error: Instance $INSTANCE IP not configured."
    echo "Set SYSMON_INSTANCE${INSTANCE}_IP or configure [instances] in config/sega.toml."
    exit 1
fi

echo "============================================================"
echo "Full Testing Pipeline - Instance $INSTANCE ($IP)"
echo "============================================================"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Mode: $([ "$QUICK_MODE" = true ] && echo "Quick" || echo "Full")"
[ -n "$PROJECT" ] && echo "Project: $PROJECT"
echo ""

# Track results
PHASE1_STATUS="PENDING"
PHASE2_STATUS="PENDING"
PHASE3_STATUS="SKIPPED"

# =============================================================================
# Phase 1: Health Check
# =============================================================================
echo "============================================================"
echo "PHASE 1: Health Check"
echo "============================================================"

if [ -n "$PROJECT" ]; then
    echo "Checking health for: $PROJECT"
    sega health --project "$PROJECT" --host "$IP" 2>/dev/null
else
    # Run full health check script
    if [ -f "$SCRIPT_DIR/ec2-health-check.sh" ]; then
        "$SCRIPT_DIR/ec2-health-check.sh" --instance "$INSTANCE" --quick
    else
        # Fallback to sega health
        sega health --all-services --host "$IP" 2>/dev/null
    fi
fi

if [ $? -eq 0 ]; then
    PHASE1_STATUS="PASSED"
    echo -e "\n[PHASE 1] Health Check: PASSED"
else
    PHASE1_STATUS="FAILED"
    echo -e "\n[PHASE 1] Health Check: FAILED"
    echo "Fix health issues before proceeding to API testing."

    # Show summary and exit
    echo ""
    echo "============================================================"
    echo "Pipeline Summary"
    echo "============================================================"
    echo "Phase 1 (Health):  $PHASE1_STATUS"
    echo "Phase 2 (API):     NOT RUN"
    echo "Phase 3 (Browser): NOT RUN"
    exit 1
fi

# =============================================================================
# Phase 2: API Testing
# =============================================================================
echo ""
echo "============================================================"
echo "PHASE 2: API Testing"
echo "============================================================"

if [ "$QUICK_MODE" = true ]; then
    echo "Quick mode: Running health-only API checks"
    if [ -n "$PROJECT" ]; then
        sega test-api "$PROJECT" --host "$IP" --health-only 2>/dev/null
    else
        sega test-api --host "$IP" --health-only 2>/dev/null
    fi
else
    echo "Running comprehensive API endpoint tests"
    if [ -n "$PROJECT" ]; then
        sega test-api "$PROJECT" --host "$IP" 2>/dev/null
    else
        sega test-api --host "$IP" 2>/dev/null
    fi
fi

if [ $? -eq 0 ]; then
    PHASE2_STATUS="PASSED"
    echo -e "\n[PHASE 2] API Testing: PASSED"
else
    PHASE2_STATUS="FAILED"
    echo -e "\n[PHASE 2] API Testing: FAILED"
fi

# =============================================================================
# Phase 3: Browser Testing
# =============================================================================
if [ "$SKIP_BROWSER" = true ] || [ "$QUICK_MODE" = true ]; then
    PHASE3_STATUS="SKIPPED"
    echo ""
    echo "============================================================"
    echo "PHASE 3: Browser Testing (SKIPPED)"
    echo "============================================================"
    echo "Browser tests skipped. Run manually with:"
    echo "  sega test browser --project <name> --type e2e"
else
    echo ""
    echo "============================================================"
    echo "PHASE 3: Browser Testing"
    echo "============================================================"

    if [ -n "$PROJECT" ]; then
        echo "Running browser tests for: $PROJECT"
        sega test browser --project "$PROJECT" --type e2e 2>/dev/null

        if [ $? -eq 0 ]; then
            PHASE3_STATUS="PASSED"
        else
            PHASE3_STATUS="FAILED"
        fi
    else
        PHASE3_STATUS="MANUAL"
        echo "Browser tests require specific project. Run manually:"
        echo "  sega test browser --project <name> --type e2e"
        echo ""
        echo "Available test types: e2e, visual, a11y, performance, all"
    fi
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "============================================================"
echo "Pipeline Summary"
echo "============================================================"
echo "Instance:          $INSTANCE ($IP)"
echo "Timestamp:         $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""
echo "Phase 1 (Health):  $PHASE1_STATUS"
echo "Phase 2 (API):     $PHASE2_STATUS"
echo "Phase 3 (Browser): $PHASE3_STATUS"
echo ""

# Exit with appropriate code
if [ "$PHASE1_STATUS" = "FAILED" ] || [ "$PHASE2_STATUS" = "FAILED" ] || [ "$PHASE3_STATUS" = "FAILED" ]; then
    echo "Pipeline: FAILED"
    exit 1
else
    echo "Pipeline: SUCCESS"
    exit 0
fi
