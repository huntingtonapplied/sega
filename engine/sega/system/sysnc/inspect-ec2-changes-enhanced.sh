#!/bin/bash
# ============================================================================
# EC2 Changes Inspector - Enhanced Version
# ============================================================================
# PURPOSE:
#   Enhanced inspection with lane separation validation and full file lists.
#   NO CHANGES ARE MADE - this is purely informational.
#
# IMPROVEMENTS OVER BASIC VERSION:
#   - No truncation (shows ALL files)
#   - Lane separation validation (Group 1 vs Group 2 in shared resources)
#   - Detailed tracker/human and spro breakdowns
#   - Project group tagging in file lists
#
# USAGE:
#   ./inspect-ec2-changes-enhanced.sh
#
# OUTPUT:
#   Generates detailed report in /tmp/ec2-inspection-enhanced-[timestamp].txt
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# EC2 configuration
# Values come from the environment: set SYSMON_INSTANCE*_IP / SYSMON_SSH_KEY,
# or configure [instances] in config/sega.toml (injected by the sega CLI).
SSH_KEY="${SYSMON_SSH_KEY:-${SSH_KEY_PATH:-}}"
IP1="${SYSMON_INSTANCE1_IP:-${INSTANCE1_IP:-}}"
IP2="${SYSMON_INSTANCE2_IP:-${INSTANCE2_IP:-}}"
if [[ -z "$SSH_KEY" || -z "$IP1" || -z "$IP2" ]]; then
    echo "ERROR: instance configuration not set." >&2
    echo "Set SYSMON_INSTANCE1_IP/SYSMON_INSTANCE2_IP and SYSMON_SSH_KEY, or configure [instances] in config/sega.toml and run via the sega CLI." >&2
    exit 1
fi
INSTANCE1_HOST="${INSTANCE1_USER:-ubuntu}@${IP1}"
INSTANCE2_HOST="${INSTANCE2_USER:-ubuntu}@${IP2}"

# Project groups (pipe-separated regex alternations, e.g. "atlas|hermes|orion")
# Set SYSNC_GROUP1_PROJECTS / SYSNC_GROUP2_PROJECTS to enable lane validation
# (injected from [instances].projects in config/sega.toml by the sega CLI).
GROUP1_PROJECTS="${SYSNC_GROUP1_PROJECTS:-__no_group1_projects__}"
GROUP2_PROJECTS="${SYSNC_GROUP2_PROJECTS:-__no_group2_projects__}"
if [[ "$GROUP1_PROJECTS" == "__no_group1_projects__" || "$GROUP2_PROJECTS" == "__no_group2_projects__" ]]; then
    echo "WARNING: SYSNC_GROUP1_PROJECTS / SYSNC_GROUP2_PROJECTS not set; lane validation will be incomplete." >&2
fi

# Output file
REPORT="/tmp/ec2-inspection-enhanced-$(date +%Y%m%d_%H%M%S).txt"

echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${WHITE}  EC2 CHANGES INSPECTOR - ENHANCED${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# Verify SSH key
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ SSH key not found: $SSH_KEY${NC}"
    exit 1
fi
chmod 600 "$SSH_KEY"

{
    echo "EC2 CHANGES INSPECTION REPORT - ENHANCED"
    echo "========================================="
    echo "Generated: $(date)"
    echo "Enhancements: Full file lists, lane separation validation, shared resource tracking"
    echo

    # Helper function to analyze shared resources
    analyze_shared_resources() {
        local instance_name=$1
        local status=$2
        local expected_group=$3

        echo "  Shared Resources Analysis (tracker/human + spro):"
        echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        # tracker/human files
        local sesh_files=$(echo "$status" | grep "tracker/human/" || echo "")
        if [ -n "$sesh_files" ]; then
            echo
            echo "  tracker/human files:"
            echo "$sesh_files" | while read -r line; do
                local file=$(echo "$line" | awk '{print $2}')
                local group_tag=""

                if echo "$file" | grep -qiE "($GROUP1_PROJECTS|GROUP1|GROUP_1)"; then
                    group_tag="[GROUP 1]"
                elif echo "$file" | grep -qiE "($GROUP2_PROJECTS|GROUP2|GROUP_2)"; then
                    group_tag="[GROUP 2]"
                else
                    group_tag="[SHARED]"
                fi

                printf "    %-60s %s\n" "$file" "$group_tag"
            done
        fi

        # spro files
        local spro_files=$(echo "$status" | grep "spro/" || echo "")
        if [ -n "$spro_files" ]; then
            echo
            echo "  spro files:"
            echo "$spro_files" | while read -r line; do
                local file=$(echo "$line" | awk '{print $2}')
                local group_tag=""

                if echo "$file" | grep -qiE "($GROUP1_PROJECTS|GROUP1|GROUP_1)"; then
                    group_tag="[GROUP 1]"
                elif echo "$file" | grep -qiE "($GROUP2_PROJECTS|GROUP2|GROUP_2)"; then
                    group_tag="[GROUP 2]"
                else
                    group_tag="[SHARED]"
                fi

                printf "    %-60s %s\n" "$file" "$group_tag"
            done
        fi

        echo
    }

    # Local changes
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "LOCAL SYSTEM CHANGES"
    echo "Expected: Infrastructure (orion, dispatcher, docs/guides)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    cd ~/fleet
    LOCAL_STATUS=$(git status --porcelain 2>&1)

    if [ -z "$LOCAL_STATUS" ]; then
        echo "✓ No changes on local system"
    else
        LOCAL_COUNT=$(echo "$LOCAL_STATUS" | wc -l)
        echo "Total files changed: $LOCAL_COUNT"
        echo

        echo "Summary by status:"
        echo "$LOCAL_STATUS" | cut -c1-2 | sort | uniq -c
        echo

        echo "Top directories:"
        echo "$LOCAL_STATUS" | awk '{print $2}' | sed 's/\/[^/]*$//' | sort | uniq -c | sort -rn | head -15
        echo

        echo "Infrastructure files (orion, dispatcher):"
        echo "$LOCAL_STATUS" | grep -E "(^...(orion|dispatcher)/)" | head -20
        local infra_count=$(echo "$LOCAL_STATUS" | grep -cE "(^...(orion|dispatcher)/)" || echo "0")
        if [ "$infra_count" -gt 20 ]; then
            echo "  ... and $((infra_count - 20)) more infrastructure files"
        fi
    fi

    echo
    echo

    # Instance 1 changes
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "INSTANCE 1 (fleet-prod-01 @ ${INSTANCE1_HOST#ubuntu@})"
    echo "Expected: Healer Workers + Project Group 1 + Shared Resources (Group 1 focus)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    I1_STATUS=$(ssh -i "$SSH_KEY" "$INSTANCE1_HOST" "cd ~/fleet && git status --porcelain 2>&1" || echo "SSH_FAILED")

    if [ "$I1_STATUS" = "SSH_FAILED" ]; then
        echo "❌ Could not connect to instance 1"
    elif [ -z "$I1_STATUS" ]; then
        echo "✓ No changes on instance 1"
    else
        I1_COUNT=$(echo "$I1_STATUS" | wc -l)
        echo "Total files changed: $I1_COUNT"
        echo

        echo "Summary by status:"
        echo "$I1_STATUS" | cut -c1-2 | sort | uniq -c
        echo

        echo "Project Group 1 files:"
        echo "$I1_STATUS" | grep -E "($GROUP1_PROJECTS)/" || echo "  (none)"
        echo

        echo "Healer worker files:"
        echo "$I1_STATUS" | grep "docs/healer/workers/" | head -15 || echo "  (none)"
        local healer_count=$(echo "$I1_STATUS" | grep -c "docs/healer/workers/" || echo "0")
        if [ "$healer_count" -gt 15 ]; then
            echo "  ... and $((healer_count - 15)) more healer worker files"
        fi
        echo

        analyze_shared_resources "Instance 1" "$I1_STATUS" "GROUP 1"
    fi

    echo
    echo

    # Instance 2 changes
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "INSTANCE 2 (fleet-prod-02 @ ${INSTANCE2_HOST#ubuntu@})"
    echo "Expected: Surgeon Workers + Project Group 2 + Shared Resources (Group 2 focus)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    I2_STATUS=$(ssh -i "$SSH_KEY" "$INSTANCE2_HOST" "cd ~/fleet && git status --porcelain 2>&1" || echo "SSH_FAILED")

    if [ "$I2_STATUS" = "SSH_FAILED" ]; then
        echo "❌ Could not connect to instance 2"
    elif [ -z "$I2_STATUS" ]; then
        echo "✓ No changes on instance 2"
    else
        I2_COUNT=$(echo "$I2_STATUS" | wc -l)
        echo "Total files changed: $I2_COUNT"
        echo

        echo "Summary by status:"
        echo "$I2_STATUS" | cut -c1-2 | sort | uniq -c
        echo

        echo "Project Group 2 files:"
        echo "$I2_STATUS" | grep -E "($GROUP2_PROJECTS)/" || echo "  (none)"
        echo

        echo "Surgeon worker files:"
        echo "$I2_STATUS" | grep "docs/surgeon/workers/" | head -20 || echo "  (none)"
        local surgeon_count=$(echo "$I2_STATUS" | grep -c "docs/surgeon/workers/" || echo "0")
        if [ "$surgeon_count" -gt 20 ]; then
            echo "  ... and $((surgeon_count - 20)) more surgeon worker files"
        fi
        echo

        analyze_shared_resources "Instance 2" "$I2_STATUS" "GROUP 2"
    fi

    echo
    echo

    # Lane Separation Validation
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "LANE SEPARATION VALIDATION"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    if [ -n "$I1_STATUS" ] && [ "$I1_STATUS" != "SSH_FAILED" ] && \
       [ -n "$I2_STATUS" ] && [ "$I2_STATUS" != "SSH_FAILED" ]; then

        # Check for Group 1 violations on Instance 2
        local i2_group1_violations=$(echo "$I2_STATUS" | grep -E "($GROUP1_PROJECTS|GROUP1|GROUP_1)" | grep -v "\.claude/settings" || echo "")
        if [ -n "$i2_group1_violations" ]; then
            echo "⚠️  Instance 2 has Group 1 files (expected Group 2 only):"
            echo "$i2_group1_violations" | sed 's/^/  /'
            echo
        fi

        # Check for Group 2 violations on Instance 1
        local i1_group2_violations=$(echo "$I1_STATUS" | grep -E "($GROUP2_PROJECTS|GROUP2|GROUP_2)" | grep -v "\.claude/settings" || echo "")
        if [ -n "$i1_group2_violations" ]; then
            echo "⚠️  Instance 1 has Group 2 files (expected Group 1 only):"
            echo "$i1_group2_violations" | sed 's/^/  /'
            echo
        fi

        if [ -z "$i2_group1_violations" ] && [ -z "$i1_group2_violations" ]; then
            echo "✅ Lane separation is PERFECT - each instance working on correct project group"
        fi
    fi

    echo
    echo

    # Conflict detection (same as basic version)
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "CONFLICT ANALYSIS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    if [ -n "$LOCAL_STATUS" ] && [ -n "$I1_STATUS" ] && [ "$I1_STATUS" != "SSH_FAILED" ]; then
        LOCAL_FILES=$(echo "$LOCAL_STATUS" | awk '{print $2}' | sort)
        I1_FILES=$(echo "$I1_STATUS" | awk '{print $2}' | sort)
        CONFLICTS_LOCAL_I1=$(comm -12 <(echo "$LOCAL_FILES") <(echo "$I1_FILES") || true)

        if [ -n "$CONFLICTS_LOCAL_I1" ]; then
            echo "⚠️  Files modified on BOTH local and instance 1:"
            echo "$CONFLICTS_LOCAL_I1" | sed 's/^/  - /'
            echo
        fi
    fi

    if [ -n "$LOCAL_STATUS" ] && [ -n "$I2_STATUS" ] && [ "$I2_STATUS" != "SSH_FAILED" ]; then
        LOCAL_FILES=$(echo "$LOCAL_STATUS" | awk '{print $2}' | sort)
        I2_FILES=$(echo "$I2_STATUS" | awk '{print $2}' | sort)
        CONFLICTS_LOCAL_I2=$(comm -12 <(echo "$LOCAL_FILES") <(echo "$I2_FILES") || true)

        if [ -n "$CONFLICTS_LOCAL_I2" ]; then
            echo "⚠️  Files modified on BOTH local and instance 2:"
            echo "$CONFLICTS_LOCAL_I2" | sed 's/^/  - /'
            echo
        fi
    fi

    if [ -n "$I1_STATUS" ] && [ "$I1_STATUS" != "SSH_FAILED" ] && \
       [ -n "$I2_STATUS" ] && [ "$I2_STATUS" != "SSH_FAILED" ]; then
        I1_FILES=$(echo "$I1_STATUS" | awk '{print $2}' | sort)
        I2_FILES=$(echo "$I2_STATUS" | awk '{print $2}' | sort)
        CONFLICTS_I1_I2=$(comm -12 <(echo "$I1_FILES") <(echo "$I2_FILES") || true)

        if [ -n "$CONFLICTS_I1_I2" ]; then
            echo "⚠️  Files modified on BOTH instance 1 and instance 2:"
            echo "$CONFLICTS_I1_I2" | sed 's/^/  - /'
            echo
        fi
    fi

    # Three-way conflicts
    if [ -n "$LOCAL_STATUS" ] && [ -n "$I1_STATUS" ] && [ "$I1_STATUS" != "SSH_FAILED" ] && \
       [ -n "$I2_STATUS" ] && [ "$I2_STATUS" != "SSH_FAILED" ]; then
        LOCAL_FILES=$(echo "$LOCAL_STATUS" | awk '{print $2}' | sort)
        I1_FILES=$(echo "$I1_STATUS" | awk '{print $2}' | sort)
        I2_FILES=$(echo "$I2_STATUS" | awk '{print $2}' | sort)

        THREE_WAY=$(comm -12 <(comm -12 <(echo "$LOCAL_FILES") <(echo "$I1_FILES")) <(echo "$I2_FILES") || true)

        if [ -n "$THREE_WAY" ]; then
            echo "🔥 FILES MODIFIED ON ALL THREE SYSTEMS (needs careful merge):"
            echo "$THREE_WAY" | sed 's/^/  - /'
            echo
        fi
    fi

    if [ -z "$CONFLICTS_LOCAL_I1" ] && [ -z "$CONFLICTS_LOCAL_I2" ] && \
       [ -z "$CONFLICTS_I1_I2" ] && [ -z "$THREE_WAY" ]; then
        echo "✓ No conflicts detected - all changes are on different files"
    fi

    echo
    echo

    # Recommendations
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "RECOMMENDATIONS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    if [ -z "$LOCAL_STATUS" ] && [ -z "$I1_STATUS" ] && [ -z "$I2_STATUS" ]; then
        echo "✅ No consolidation needed - all systems are clean"
    else
        echo "Next Steps:"
        echo "1. Review this enhanced report carefully"
        echo "2. Note the lane separation validation results"
        echo "3. Follow procedure: ~/fleet/docs/guides/procedures/EC2_CONSOLIDATION_PROCEDURE.md"
        echo "4. Use Phase 3 commands to transfer files from instances to local"
        echo "5. Resolve any conflicts using Phase 4 strategies"
        echo "6. Push from local system after consolidation"
    fi

    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "END OF ENHANCED REPORT"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

} | tee "$REPORT"

echo
echo -e "${GREEN}Enhanced report saved to: $REPORT${NC}"
echo
echo -e "${CYAN}Quick actions:${NC}"
echo "  View report:  less $REPORT"
echo "  Follow procedure: less ~/fleet/docs/guides/procedures/EC2_CONSOLIDATION_PROCEDURE.md"
echo
