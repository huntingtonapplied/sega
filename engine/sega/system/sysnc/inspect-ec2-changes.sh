#!/bin/bash
# ============================================================================
# EC2 Changes Inspector (Read-Only)
# ============================================================================
# PURPOSE:
#   Inspect git changes across all three systems and generate a report.
#   NO CHANGES ARE MADE - this is purely informational.
#
# USAGE:
#   ./inspect-ec2-changes.sh
#
# OUTPUT:
#   Generates detailed report in /tmp/ec2-inspection-report-[timestamp].txt
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
IP3="${SYSMON_INSTANCE3_IP:-${INSTANCE3_IP:-}}"
if [[ -z "$SSH_KEY" || -z "$IP1" || -z "$IP2" || -z "$IP3" ]]; then
    echo "ERROR: instance configuration not set." >&2
    echo "Set SYSMON_INSTANCE1_IP/SYSMON_INSTANCE2_IP/SYSMON_INSTANCE3_IP and SYSMON_SSH_KEY, or configure [instances] in config/sega.toml and run via the sega CLI." >&2
    exit 1
fi
INSTANCE1_HOST="${INSTANCE1_USER:-ubuntu}@${IP1}"
INSTANCE2_HOST="${INSTANCE2_USER:-ubuntu}@${IP2}"
INSTANCE3_HOST="${INSTANCE3_USER:-ubuntu}@${IP3}"

# Per-instance project groups as regex alternations (e.g. "atlas|hermes|orion");
# injected from [instances].projects in config/sega.toml by the sega CLI.
GROUP1_RE="${SYSNC_GROUP1_PROJECTS:-__no_group1_projects__}"
GROUP2_RE="${SYSNC_GROUP2_PROJECTS:-__no_group2_projects__}"
GROUP3_RE="${SYSNC_GROUP3_PROJECTS:-__no_group3_projects__}"

# Output file
REPORT="/tmp/ec2-inspection-report-$(date +%Y%m%d_%H%M%S).txt"

echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${WHITE}  EC2 CHANGES INSPECTOR (READ-ONLY)${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# Verify SSH key
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ SSH key not found: $SSH_KEY${NC}"
    exit 1
fi
chmod 600 "$SSH_KEY"

{
    echo "EC2 CHANGES INSPECTION REPORT"
    echo "=============================="
    echo "Generated: $(date)"
    echo "Procedure: See ~/fleet/docs/guides/procedures/EC2_CONSOLIDATION_PROCEDURE.md"
    echo
    echo

    # Local changes
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "LOCAL SYSTEM CHANGES"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    cd ~/fleet
    LOCAL_STATUS=$(git status --porcelain 2>&1)

    if [ -z "$LOCAL_STATUS" ]; then
        echo "✓ No changes on local system"
    else
        echo "Modified files:"
        echo "$LOCAL_STATUS" | head -50
        LOCAL_COUNT=$(echo "$LOCAL_STATUS" | wc -l)
        if [ $LOCAL_COUNT -gt 50 ]; then
            echo "... and $((LOCAL_COUNT - 50)) more files"
        fi
        echo
        echo "Summary by status:"
        echo "$LOCAL_STATUS" | cut -c1-2 | sort | uniq -c
        echo
        echo "File breakdown:"
        echo "$LOCAL_STATUS" | awk '{print $2}' | sed 's/\/[^/]*$//' | sort | uniq -c | sort -rn | head -10
    fi

    echo
    echo

    # Instance 1 changes
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "INSTANCE 1 (fleet-prod-01 @ ${INSTANCE1_HOST#ubuntu@})"
    echo "Expected: Project Group 1 + Surgeon Workers"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    I1_STATUS=$(ssh -i "$SSH_KEY" "$INSTANCE1_HOST" "cd ~/fleet && git status --porcelain 2>&1" || echo "SSH_FAILED")

    if [ "$I1_STATUS" = "SSH_FAILED" ]; then
        echo "❌ Could not connect to instance 1"
    elif [ -z "$I1_STATUS" ]; then
        echo "✓ No changes on instance 1"
    else
        echo "Modified files:"
        echo "$I1_STATUS" | head -50
        I1_COUNT=$(echo "$I1_STATUS" | wc -l)
        if [ $I1_COUNT -gt 50 ]; then
            echo "... and $((I1_COUNT - 50)) more files"
        fi
        echo
        echo "Summary by status:"
        echo "$I1_STATUS" | cut -c1-2 | sort | uniq -c
        echo
        echo "File breakdown:"
        echo "$I1_STATUS" | awk '{print $2}' | sed 's/\/[^/]*$//' | sort | uniq -c | sort -rn | head -10
        echo
        echo "Project Group 1 files:"
        echo "$I1_STATUS" | grep -E "(${GROUP1_RE})/" || echo "  (none)"
        echo
        echo "Surgeon worker files:"
        echo "$I1_STATUS" | grep "docs/surgeon/workers/" || echo "  (none)"
    fi

    echo
    echo

    # Instance 2 changes
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "INSTANCE 2 (fleet-prod-02 @ ${INSTANCE2_HOST#ubuntu@})"
    echo "Expected: Project Group 2"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    I2_STATUS=$(ssh -i "$SSH_KEY" "$INSTANCE2_HOST" "cd ~/fleet && git status --porcelain 2>&1" || echo "SSH_FAILED")

    if [ "$I2_STATUS" = "SSH_FAILED" ]; then
        echo "❌ Could not connect to instance 2"
    elif [ -z "$I2_STATUS" ]; then
        echo "✓ No changes on instance 2"
    else
        echo "Modified files:"
        echo "$I2_STATUS" | head -50
        I2_COUNT=$(echo "$I2_STATUS" | wc -l)
        if [ $I2_COUNT -gt 50 ]; then
            echo "... and $((I2_COUNT - 50)) more files"
        fi
        echo
        echo "Summary by status:"
        echo "$I2_STATUS" | cut -c1-2 | sort | uniq -c
        echo
        echo "File breakdown:"
        echo "$I2_STATUS" | awk '{print $2}' | sed 's/\/[^/]*$//' | sort | uniq -c | sort -rn | head -10
        echo
        echo "Project Group 2 files:"
        echo "$I2_STATUS" | grep -E "(${GROUP2_RE})/" || echo "  (none)"
    fi

    echo
    echo

    # Instance 3 changes
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "INSTANCE 3 (fleet-prod-03 @ ${INSTANCE3_HOST#ubuntu@})"
    echo "Expected: Project Group 3"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    I3_STATUS=$(ssh -i "$SSH_KEY" "$INSTANCE3_HOST" "cd ~/fleet && git status --porcelain 2>&1" || echo "SSH_FAILED")

    if [ "$I3_STATUS" = "SSH_FAILED" ]; then
        echo "❌ Could not connect to instance 3"
    elif [ -z "$I3_STATUS" ]; then
        echo "✓ No changes on instance 3"
    else
        echo "Modified files:"
        echo "$I3_STATUS" | head -50
        I3_COUNT=$(echo "$I3_STATUS" | wc -l)
        if [ $I3_COUNT -gt 50 ]; then
            echo "... and $((I3_COUNT - 50)) more files"
        fi
        echo
        echo "Summary by status:"
        echo "$I3_STATUS" | cut -c1-2 | sort | uniq -c
        echo
        echo "File breakdown:"
        echo "$I3_STATUS" | awk '{print $2}' | sed 's/\/[^/]*$//' | sort | uniq -c | sort -rn | head -10
        echo
        echo "Project Group 3 files:"
        echo "$I3_STATUS" | grep -E "(${GROUP3_RE})/" || echo "  (none)"
    fi

    echo
    echo

    # Conflict detection
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

    if [ -n "$LOCAL_STATUS" ] && [ -n "$I3_STATUS" ] && [ "$I3_STATUS" != "SSH_FAILED" ]; then
        LOCAL_FILES=$(echo "$LOCAL_STATUS" | awk '{print $2}' | sort)
        I3_FILES=$(echo "$I3_STATUS" | awk '{print $2}' | sort)
        CONFLICTS_LOCAL_I3=$(comm -12 <(echo "$LOCAL_FILES") <(echo "$I3_FILES") || true)

        if [ -n "$CONFLICTS_LOCAL_I3" ]; then
            echo "⚠️  Files modified on BOTH local and instance 3:"
            echo "$CONFLICTS_LOCAL_I3" | sed 's/^/  - /'
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

    if [ -n "$I1_STATUS" ] && [ "$I1_STATUS" != "SSH_FAILED" ] && \
       [ -n "$I3_STATUS" ] && [ "$I3_STATUS" != "SSH_FAILED" ]; then
        I1_FILES=$(echo "$I1_STATUS" | awk '{print $2}' | sort)
        I3_FILES=$(echo "$I3_STATUS" | awk '{print $2}' | sort)
        CONFLICTS_I1_I3=$(comm -12 <(echo "$I1_FILES") <(echo "$I3_FILES") || true)

        if [ -n "$CONFLICTS_I1_I3" ]; then
            echo "⚠️  Files modified on BOTH instance 1 and instance 3:"
            echo "$CONFLICTS_I1_I3" | sed 's/^/  - /'
            echo
        fi
    fi

    if [ -n "$I2_STATUS" ] && [ "$I2_STATUS" != "SSH_FAILED" ] && \
       [ -n "$I3_STATUS" ] && [ "$I3_STATUS" != "SSH_FAILED" ]; then
        I2_FILES=$(echo "$I2_STATUS" | awk '{print $2}' | sort)
        I3_FILES=$(echo "$I3_STATUS" | awk '{print $2}' | sort)
        CONFLICTS_I2_I3=$(comm -12 <(echo "$I2_FILES") <(echo "$I3_FILES") || true)

        if [ -n "$CONFLICTS_I2_I3" ]; then
            echo "⚠️  Files modified on BOTH instance 2 and instance 3:"
            echo "$CONFLICTS_I2_I3" | sed 's/^/  - /'
            echo
        fi
    fi

    # Four-way conflicts (all systems)
    if [ -n "$LOCAL_STATUS" ] && [ -n "$I1_STATUS" ] && [ "$I1_STATUS" != "SSH_FAILED" ] && \
       [ -n "$I2_STATUS" ] && [ "$I2_STATUS" != "SSH_FAILED" ] && \
       [ -n "$I3_STATUS" ] && [ "$I3_STATUS" != "SSH_FAILED" ]; then
        LOCAL_FILES=$(echo "$LOCAL_STATUS" | awk '{print $2}' | sort)
        I1_FILES=$(echo "$I1_STATUS" | awk '{print $2}' | sort)
        I2_FILES=$(echo "$I2_STATUS" | awk '{print $2}' | sort)
        I3_FILES=$(echo "$I3_STATUS" | awk '{print $2}' | sort)

        FOUR_WAY=$(comm -12 <(comm -12 <(comm -12 <(echo "$LOCAL_FILES") <(echo "$I1_FILES")) <(echo "$I2_FILES")) <(echo "$I3_FILES") || true)

        if [ -n "$FOUR_WAY" ]; then
            echo "🔥 FILES MODIFIED ON ALL FOUR SYSTEMS (needs careful merge):"
            echo "$FOUR_WAY" | sed 's/^/  - /'
            echo
        fi
    fi

    if [ -z "$CONFLICTS_LOCAL_I1" ] && [ -z "$CONFLICTS_LOCAL_I2" ] && [ -z "$CONFLICTS_LOCAL_I3" ] && \
       [ -z "$CONFLICTS_I1_I2" ] && [ -z "$CONFLICTS_I1_I3" ] && [ -z "$CONFLICTS_I2_I3" ] && [ -z "$FOUR_WAY" ]; then
        echo "✓ No conflicts detected - all changes are on different files"
    fi

    echo
    echo

    # Recommendations
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "RECOMMENDATIONS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    if [ -z "$LOCAL_STATUS" ] && [ -z "$I1_STATUS" ] && [ -z "$I2_STATUS" ] && [ -z "$I3_STATUS" ]; then
        echo "✅ No consolidation needed - all systems are clean"
    else
        echo "Next Steps:"
        echo "1. Review this report carefully"
        echo "2. Follow procedure: ~/fleet/docs/guides/procedures/EC2_CONSOLIDATION_PROCEDURE.md"
        echo "3. Use Phase 3 commands to transfer files from instances to local"
        echo "4. Resolve any conflicts using Phase 4 strategies"
        echo "5. Push from local system after consolidation"
    fi

    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "END OF REPORT"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

} | tee "$REPORT"

echo
echo -e "${GREEN}Report saved to: $REPORT${NC}"
echo
echo -e "${CYAN}Quick actions:${NC}"
echo "  View report:  less $REPORT"
echo "  Copy report:  cat $REPORT | pbcopy"
echo "  Follow procedure: less ~/fleet/docs/guides/procedures/EC2_CONSOLIDATION_PROCEDURE.md"
echo
