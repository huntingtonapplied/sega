#!/bin/bash
# ============================================================================
# Multi-System Consolidation with Submodule Support
# ============================================================================
# PURPOSE:
#   Properly handle git operations across submodules and parent module.
#
# WORKFLOW PER SYSTEM:
#   1. For each submodule with changes:
#      - git stash
#      - git pull
#      - git stash pop
#      - git add . && git commit && git push
#   2. In parent module:
#      - git stash (for non-submodule changes in top-level tool dirs)
#      - git pull (updates submodule references)
#      - git stash pop
#      - git add . && git commit && git push
#
# EXECUTION ORDER:
#   Phase 1: Instance 2 (Group 2 projects + Surgeon)
#   Phase 2: Instance 1 (Group 1 projects + Healer) - pulls Instance 2's work
#   Phase 3: Local (Infrastructure) - pulls all distributed work
#
# USAGE:
#   ./consolidate-with-submodules.sh [--dry-run] [--phase N] [--system SYSTEM]
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

# Configuration
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
INSTANCE1="${INSTANCE1_USER:-ubuntu}@${IP1}"
INSTANCE2="${INSTANCE2_USER:-ubuntu}@${IP2}"
LOCAL_FLEET="$HOME/fleet"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Parse arguments
DRY_RUN=false
SPECIFIC_PHASE=""
SPECIFIC_SYSTEM=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --phase)
            SPECIFIC_PHASE="$2"
            shift 2
            ;;
        --system)
            SPECIFIC_SYSTEM="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--phase N] [--system local|i1|i2]"
            exit 2
            ;;
    esac
done

# Verify SSH key
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ SSH key not found: $SSH_KEY${NC}"
    exit 3
fi
chmod 600 "$SSH_KEY"

# Logging
LOG_FILE="$LOCAL_FLEET/dispatcher/logs/consolidate-submodules-${TIMESTAMP}.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Helper: Show what would be done
show_command() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN]${NC} $*"
        log "DRY RUN: $*"
    else
        echo -e "${CYAN}$*${NC}"
        log "EXECUTING: $*"
    fi
}

# Process submodules on a specific host
process_submodules_remote() {
    local host="$1"
    local host_name="$2"
    local commit_message_prefix="$3"

    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  Processing Submodules on $host_name${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # Get list of submodules with changes
    show_command "Finding submodules with changes on $host_name..."

    local submodules_script='
cd ~/fleet
git submodule foreach --quiet '\''
    if [ -n "$(git status --porcelain)" ]; then
        echo $sm_path
    fi
'\''
'

    if [ "$DRY_RUN" = false ]; then
        local changed_submodules=$(ssh -i "$SSH_KEY" "$host" "$submodules_script")

        if [ -z "$changed_submodules" ]; then
            echo -e "${GREEN}✓ No submodules have changes${NC}"
        else
            echo -e "${CYAN}Submodules with changes:${NC}"
            echo "$changed_submodules" | sed 's/^/  - /'
            echo

            # Process each changed submodule
            while IFS= read -r submodule; do
                if [ -n "$submodule" ]; then
                    echo -e "${YELLOW}Processing submodule: $submodule${NC}"

                    # Show status
                    echo -e "${CYAN}Status:${NC}"
                    ssh -i "$SSH_KEY" "$host" "cd ~/fleet/$submodule && git status --short" | head -10

                    # Stash
                    show_command "  Stashing changes in $submodule..."
                    ssh -i "$SSH_KEY" "$host" "cd ~/fleet/$submodule && git stash push -m 'pre-consolidation-${TIMESTAMP}' || echo 'Nothing to stash'"

                    # Pull
                    show_command "  Pulling latest in $submodule..."
                    ssh -i "$SSH_KEY" "$host" "cd ~/fleet/$submodule && git pull origin main"

                    # Pop stash
                    show_command "  Reapplying changes in $submodule..."
                    ssh -i "$SSH_KEY" "$host" "cd ~/fleet/$submodule && git stash pop || echo 'No stash to pop'"

                    # Check for conflicts
                    local conflicts=$(ssh -i "$SSH_KEY" "$host" "cd ~/fleet/$submodule && git status --porcelain | grep '^UU' | wc -l" || echo "0")

                    if [ "$conflicts" != "0" ]; then
                        echo -e "${RED}⚠️  CONFLICTS in $submodule!${NC}"
                        ssh -i "$SSH_KEY" "$host" "cd ~/fleet/$submodule && git status --porcelain | grep '^UU'"
                        exit 1
                    fi

                    # Commit
                    show_command "  Committing changes in $submodule..."
                    ssh -i "$SSH_KEY" "$host" "cd ~/fleet/$submodule && git add . && git commit -m 'cc52: $commit_message_prefix - $submodule work complete

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>' || echo 'Nothing to commit'"

                    # Push
                    show_command "  Pushing $submodule..."
                    ssh -i "$SSH_KEY" "$host" "cd ~/fleet/$submodule && git push origin main"

                    echo -e "${GREEN}✓ $submodule complete${NC}"
                    echo
                fi
            done <<< "$changed_submodules"
        fi
    else
        echo -e "${YELLOW}[DRY RUN] Would check for changed submodules${NC}"
    fi
}

# Process parent module on remote host
process_parent_remote() {
    local host="$1"
    local host_name="$2"
    local commit_message="$3"

    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  Processing Parent Module on $host_name${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # Show status
    echo -e "${CYAN}Parent module status:${NC}"
    if [ "$DRY_RUN" = false ]; then
        ssh -i "$SSH_KEY" "$host" "cd ~/fleet && git status --short" | head -20
    fi
    echo

    # Stash (for non-submodule top-level changes)
    show_command "Stashing parent module changes..."
    if [ "$DRY_RUN" = false ]; then
        ssh -i "$SSH_KEY" "$host" "cd ~/fleet && git stash push -m 'parent-pre-consolidation-${TIMESTAMP}' || echo 'Nothing to stash'"
    fi

    # Pull (gets submodule reference updates + other system's work)
    show_command "Pulling latest in parent module..."
    if [ "$DRY_RUN" = false ]; then
        ssh -i "$SSH_KEY" "$host" "cd ~/fleet && git pull origin main"
    fi

    # Pop stash
    show_command "Reapplying parent module changes..."
    if [ "$DRY_RUN" = false ]; then
        ssh -i "$SSH_KEY" "$host" "cd ~/fleet && git stash pop || echo 'No stash to pop'"
    fi

    # Check for conflicts
    if [ "$DRY_RUN" = false ]; then
        local conflicts=$(ssh -i "$SSH_KEY" "$host" "cd ~/fleet && git status --porcelain | grep '^UU' | wc -l" || echo "0")

        if [ "$conflicts" != "0" ]; then
            echo -e "${RED}⚠️  CONFLICTS in parent module!${NC}"
            ssh -i "$SSH_KEY" "$host" "cd ~/fleet && git status --porcelain | grep '^UU'"
            exit 1
        fi
    fi

    # Commit (includes submodule reference updates)
    show_command "Committing parent module..."
    if [ "$DRY_RUN" = false ]; then
        ssh -i "$SSH_KEY" "$host" "cd ~/fleet && git add . && git commit -m \"$commit_message\" || echo 'Nothing to commit'"
    fi

    # Push
    show_command "Pushing parent module..."
    if [ "$DRY_RUN" = false ]; then
        ssh -i "$SSH_KEY" "$host" "cd ~/fleet && git push origin main"
    fi

    echo -e "${GREEN}✓ Parent module complete${NC}"
    echo
}

# Process submodules locally
process_submodules_local() {
    local commit_message_prefix="$1"

    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  Processing Submodules on Local${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    cd "$LOCAL_FLEET"

    # Find submodules with changes
    show_command "Finding submodules with changes locally..."

    if [ "$DRY_RUN" = false ]; then
        local changed_submodules=$(git submodule foreach --quiet '
            if [ -n "$(git status --porcelain)" ]; then
                echo $sm_path
            fi
        ')

        if [ -z "$changed_submodules" ]; then
            echo -e "${GREEN}✓ No submodules have changes${NC}"
        else
            echo -e "${CYAN}Submodules with changes:${NC}"
            echo "$changed_submodules" | sed 's/^/  - /'
            echo

            # Process each changed submodule
            while IFS= read -r submodule; do
                if [ -n "$submodule" ]; then
                    echo -e "${YELLOW}Processing submodule: $submodule${NC}"

                    cd "$LOCAL_FLEET/$submodule"

                    # Show status
                    echo -e "${CYAN}Status:${NC}"
                    git status --short | head -10

                    # Stash
                    show_command "  Stashing changes in $submodule..."
                    git stash push -m "pre-consolidation-${TIMESTAMP}" || echo "Nothing to stash"

                    # Pull
                    show_command "  Pulling latest in $submodule..."
                    git pull origin main

                    # Pop stash
                    show_command "  Reapplying changes in $submodule..."
                    git stash pop || echo "No stash to pop"

                    # Check for conflicts
                    local conflicts=$(git status --porcelain | grep '^UU' | wc -l || echo "0")

                    if [ "$conflicts" != "0" ]; then
                        echo -e "${RED}⚠️  CONFLICTS in $submodule!${NC}"
                        git status --porcelain | grep '^UU'
                        exit 1
                    fi

                    # Commit
                    show_command "  Committing changes in $submodule..."
                    git add .
                    git commit -m "cc52: $commit_message_prefix - $submodule work complete

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>" || echo "Nothing to commit"

                    # Push
                    show_command "  Pushing $submodule..."
                    git push origin main

                    echo -e "${GREEN}✓ $submodule complete${NC}"
                    echo

                    cd "$LOCAL_FLEET"
                fi
            done <<< "$changed_submodules"
        fi
    else
        echo -e "${YELLOW}[DRY RUN] Would check for changed submodules${NC}"
    fi
}

# Process parent module locally
process_parent_local() {
    local commit_message="$1"

    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  Processing Parent Module on Local${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    cd "$LOCAL_FLEET"

    # Show status
    echo -e "${CYAN}Parent module status:${NC}"
    if [ "$DRY_RUN" = false ]; then
        git status --short | head -20
    fi
    echo

    # Stash
    show_command "Stashing parent module changes..."
    if [ "$DRY_RUN" = false ]; then
        git stash push -m "parent-pre-consolidation-${TIMESTAMP}" || echo "Nothing to stash"
    fi

    # Pull
    show_command "Pulling latest in parent module..."
    if [ "$DRY_RUN" = false ]; then
        git pull origin main
    fi

    # Pop stash
    show_command "Reapplying parent module changes..."
    if [ "$DRY_RUN" = false ]; then
        git stash pop || echo "No stash to pop"
    fi

    # Check for conflicts
    if [ "$DRY_RUN" = false ]; then
        local conflicts=$(git status --porcelain | grep '^UU' | wc -l || echo "0")

        if [ "$conflicts" != "0" ]; then
            echo -e "${RED}⚠️  CONFLICTS in parent module!${NC}"
            git status --porcelain | grep '^UU'
            exit 1
        fi
    fi

    # Commit
    show_command "Committing parent module..."
    if [ "$DRY_RUN" = false ]; then
        git add .
        git commit -m "$commit_message" || echo "Nothing to commit"
    fi

    # Push
    show_command "Pushing parent module..."
    if [ "$DRY_RUN" = false ]; then
        git push origin main
    fi

    echo -e "${GREEN}✓ Parent module complete${NC}"
    echo
}

# Phase 1: Instance 2
phase1_instance2() {
    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║${NC}  ${WHITE}PHASE 1: INSTANCE 2 (${INSTANCE2#ubuntu@})${NC}                        ${PURPLE}║${NC}"
    echo -e "${PURPLE}║${NC}  ${WHITE}Surgeon + Group 2 Projects + Atlas${NC}                     ${PURPLE}║${NC}"
    echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo

    # Process submodules first
    process_submodules_remote "$INSTANCE2" "Instance 2" "Group 2 projects"

    # Process parent module
    process_parent_remote "$INSTANCE2" "Instance 2" "cc52: Surgeon groups + Group 2 projects + Atlas complete

- Surgeon workers Group 1 and 2 complete
- Project Group 2 complete (all Group 2 projects)
- Atlas on Group 2 complete
- Tracker/Spro frontend prep Group 2 complete

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

    echo -e "${GREEN}✅ Phase 1 (Instance 2) Complete${NC}"
    echo
}

# Phase 2: Instance 1
phase2_instance1() {
    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║${NC}  ${WHITE}PHASE 2: INSTANCE 1 (${INSTANCE1#ubuntu@})${NC}                        ${PURPLE}║${NC}"
    echo -e "${PURPLE}║${NC}  ${WHITE}Healer + Group 1 Projects${NC}                                 ${PURPLE}║${NC}"
    echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo

    # Process submodules first
    process_submodules_remote "$INSTANCE1" "Instance 1" "Group 1 projects"

    # Process parent module
    process_parent_remote "$INSTANCE1" "Instance 1" "cc52: Healer Group 1 + Group 1 projects complete

- Healer Group 1 work on Instance 1 complete
- Project Group 1 complete (all Group 1 projects)
- Tracker/ORION frontend work Group 1 may be complete

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

    echo -e "${GREEN}✅ Phase 2 (Instance 1) Complete${NC}"
    echo
}

# Phase 3: Local
phase3_local() {
    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║${NC}  ${WHITE}PHASE 3: LOCAL${NC}                                             ${PURPLE}║${NC}"
    echo -e "${PURPLE}║${NC}  ${WHITE}ORION Productization + DISPATCHER Optimization${NC}                 ${PURPLE}║${NC}"
    echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo

    # Process submodules first (though local shouldn't have project submodule changes)
    process_submodules_local "Infrastructure"

    # Process parent module
    process_parent_local "cc52: ORION productization + DISPATCHER optimization + Distributed work consolidated

- ORION: New launcher architecture (80 new files, 20 deprecated)
- DISPATCHER: Restructured (core/, playbooks/, reports/, tracking/)
- Multi-system tooling infrastructure created
- All distributed work from instances consolidated

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

    echo -e "${GREEN}✅ Phase 3 (Local) Complete${NC}"
    echo
}

# Verification
verify_all_systems() {
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  VERIFICATION${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    if [ "$DRY_RUN" = false ]; then
        local local_commit=$(cd "$LOCAL_FLEET" && git rev-parse HEAD)
        local i1_commit=$(ssh -i "$SSH_KEY" "$INSTANCE1" "cd ~/fleet && git rev-parse HEAD" 2>/dev/null || echo "ERROR")
        local i2_commit=$(ssh -i "$SSH_KEY" "$INSTANCE2" "cd ~/fleet && git rev-parse HEAD" 2>/dev/null || echo "ERROR")

        echo "Parent module commits:"
        echo "  Local:      $local_commit"
        echo "  Instance 1: $i1_commit"
        echo "  Instance 2: $i2_commit"
        echo

        if [ "$local_commit" = "$i1_commit" ] && [ "$local_commit" = "$i2_commit" ]; then
            echo -e "${GREEN}✅ All systems at same commit!${NC}"
        else
            echo -e "${YELLOW}⚠️  Systems have different commits${NC}"
        fi
    fi
    echo
}

# Main execution
main() {
    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║${NC}  ${WHITE}MULTI-SYSTEM CONSOLIDATION WITH SUBMODULES${NC}                ${PURPLE}║${NC}"
    echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}━━━━ DRY RUN MODE ━━━━${NC}"
        echo
    fi

    log "=== Consolidation Started ==="
    log "Dry run: $DRY_RUN"

    # Execute phases
    if [ -z "$SPECIFIC_PHASE" ] || [ "$SPECIFIC_PHASE" = "1" ]; then
        if [ -z "$SPECIFIC_SYSTEM" ] || [ "$SPECIFIC_SYSTEM" = "i2" ]; then
            phase1_instance2
        fi
    fi

    if [ -z "$SPECIFIC_PHASE" ] || [ "$SPECIFIC_PHASE" = "2" ]; then
        if [ -z "$SPECIFIC_SYSTEM" ] || [ "$SPECIFIC_SYSTEM" = "i1" ]; then
            phase2_instance1
        fi
    fi

    if [ -z "$SPECIFIC_PHASE" ] || [ "$SPECIFIC_PHASE" = "3" ]; then
        if [ -z "$SPECIFIC_SYSTEM" ] || [ "$SPECIFIC_SYSTEM" = "local" ]; then
            phase3_local
        fi
    fi

    # Verify
    if [ -z "$SPECIFIC_PHASE" ]; then
        verify_all_systems
    fi

    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  ✅ CONSOLIDATION COMPLETE${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
    echo "Log file: $LOG_FILE"
    echo

    log "=== Consolidation Completed ==="
}

main
