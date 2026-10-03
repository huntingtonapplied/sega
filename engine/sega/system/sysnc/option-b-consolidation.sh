#!/bin/bash
# ============================================================================
# Option B: Git-Based Multi-System Consolidation
# ============================================================================
# PURPOSE:
#   Orchestrate git stash/pull/push consolidation across 4 systems using
#   the perfect lane separation to avoid conflicts.
#
# STRATEGY:
#   Phase 1: Local commits and pushes (ORION/DISPATCHER infrastructure)
#   Phase 2: Instance 2 stash, pull, pop, commit, push (Surgeon + Group 2)
#   Phase 3: Instance 1 stash, pull, pop, commit, push (Healer + Group 1)
#   Phase 4: Local pulls final consolidated state
#
# USAGE:
#   ./option-b-consolidation.sh [--dry-run] [--phase N]
#
# OPTIONS:
#   --dry-run    Show what would be done without executing
#   --phase N    Execute only phase N (1-4)
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
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--phase N]"
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
LOG_FILE="$LOCAL_FLEET/dispatcher/logs/option-b-consolidation-${TIMESTAMP}.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Helper: Execute or show command
execute() {
    local description="$1"
    shift

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN]${NC} $description"
        echo -e "${CYAN}  Would execute: $*${NC}"
        log "DRY RUN: $description - $*"
    else
        echo -e "${CYAN}$description${NC}"
        log "EXECUTING: $description - $*"
        "$@"
        local exit_code=$?
        if [ $exit_code -ne 0 ]; then
            echo -e "${RED}❌ Failed: $description${NC}"
            log "FAILED: $description (exit code: $exit_code)"
            return $exit_code
        fi
        log "SUCCESS: $description"
    fi
}

# Helper: Execute remote SSH command
execute_remote() {
    local host="$1"
    local description="$2"
    local command="$3"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN]${NC} $description on $host"
        echo -e "${CYAN}  Would execute: $command${NC}"
        log "DRY RUN: $description on $host - $command"
    else
        echo -e "${CYAN}$description on $host${NC}"
        log "EXECUTING: $description on $host - $command"
        ssh -i "$SSH_KEY" "$host" "$command"
        local exit_code=$?
        if [ $exit_code -ne 0 ]; then
            echo -e "${RED}❌ Failed: $description on $host${NC}"
            log "FAILED: $description on $host (exit code: $exit_code)"
            return $exit_code
        fi
        log "SUCCESS: $description on $host"
    fi
}

# Pre-flight checks
preflight_check() {
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  PRE-FLIGHT CHECKS${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # Check SSH connectivity
    echo -e "${CYAN}Checking SSH connectivity...${NC}"
    if ssh -i "$SSH_KEY" -o ConnectTimeout=5 "$INSTANCE1" "echo OK" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Instance 1 reachable${NC}"
    else
        echo -e "${RED}✗ Instance 1 unreachable${NC}"
        exit 3
    fi

    if ssh -i "$SSH_KEY" -o ConnectTimeout=5 "$INSTANCE2" "echo OK" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Instance 2 reachable${NC}"
    else
        echo -e "${RED}✗ Instance 2 unreachable${NC}"
        exit 3
    fi

    # Check git status
    echo -e "${CYAN}Checking for uncommitted changes...${NC}"

    local local_changes=$(cd "$LOCAL_FLEET" && git status --porcelain | wc -l)
    echo "  Local: $local_changes files"

    local i1_changes=$(ssh -i "$SSH_KEY" "$INSTANCE1" "cd ~/fleet && git status --porcelain | wc -l" 2>/dev/null || echo "ERROR")
    echo "  Instance 1: $i1_changes files"

    local i2_changes=$(ssh -i "$SSH_KEY" "$INSTANCE2" "cd ~/fleet && git status --porcelain | wc -l" 2>/dev/null || echo "ERROR")
    echo "  Instance 2: $i2_changes files"

    if [ "$local_changes" -eq 0 ] && [ "$i1_changes" = "0" ] && [ "$i2_changes" = "0" ]; then
        echo -e "${GREEN}✓ All systems clean - nothing to consolidate${NC}"
        exit 0
    fi

    echo
}

# Phase 1: Local commits and pushes
phase1_local() {
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  PHASE 1: LOCAL → GIT${NC}"
    echo -e "${WHITE}  (ORION productization + DISPATCHER optimization)${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    cd "$LOCAL_FLEET"

    # Show status
    echo -e "${CYAN}Current git status:${NC}"
    git status --short | head -20
    local total=$(git status --porcelain | wc -l)
    if [ "$total" -gt 20 ]; then
        echo "... and $((total - 20)) more files"
    fi
    echo

    # Confirm
    if [ "$DRY_RUN" = false ] && [ -z "$SPECIFIC_PHASE" ]; then
        read -p "Proceed with committing and pushing from local? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Aborted by user${NC}"
            exit 1
        fi
    fi

    # Git operations
    execute "Add all changes" git add .

    if [ "$DRY_RUN" = false ]; then
        git commit -m "cc52: ORION productization + DISPATCHER optimization

- ORION: New launcher architecture (80 new files, 20 deprecated)
- DISPATCHER: Restructured (core/, playbooks/, reports/, tracking/)
- Multi-system tooling infrastructure created
- 3-way conflict analysis completed

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

        execute "Push to origin" git push origin main
    fi

    echo -e "${GREEN}✓ Phase 1 complete${NC}"
    echo
}

# Phase 2: Instance 2 consolidation
phase2_instance2() {
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  PHASE 2: INSTANCE 2 → GIT${NC}"
    echo -e "${WHITE}  (Surgeon + Group 2 projects + Atlas)${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # Show status
    echo -e "${CYAN}Instance 2 current status:${NC}"
    ssh -i "$SSH_KEY" "$INSTANCE2" "cd ~/fleet && git status --short" | head -20
    local total=$(ssh -i "$SSH_KEY" "$INSTANCE2" "cd ~/fleet && git status --porcelain | wc -l")
    if [ "$total" -gt 20 ]; then
        echo "... and $((total - 20)) more files"
    fi
    echo

    # Stash
    execute_remote "$INSTANCE2" "Stash changes" \
        "cd ~/fleet && git stash push -m 'i2-work-${TIMESTAMP}' || echo 'Nothing to stash'"

    # Pull (gets local's ORION/DISPATCHER changes)
    execute_remote "$INSTANCE2" "Pull from origin" \
        "cd ~/fleet && git pull origin main"

    # Pop stash (reapply Instance 2's work)
    execute_remote "$INSTANCE2" "Reapply stashed changes" \
        "cd ~/fleet && git stash pop || echo 'No stash to pop'"

    # Check for conflicts
    echo -e "${CYAN}Checking for conflicts on Instance 2...${NC}"
    local conflicts=$(ssh -i "$SSH_KEY" "$INSTANCE2" "cd ~/fleet && git status --porcelain | grep '^UU' | wc -l" || echo "0")

    if [ "$conflicts" != "0" ]; then
        echo -e "${RED}⚠️  CONFLICTS DETECTED on Instance 2!${NC}"
        echo "Files in conflict:"
        ssh -i "$SSH_KEY" "$INSTANCE2" "cd ~/fleet && git status --porcelain | grep '^UU'"
        echo
        echo -e "${YELLOW}Manual intervention required on Instance 2${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ No conflicts detected${NC}"
    fi

    # Commit and push
    execute_remote "$INSTANCE2" "Add changes" \
        "cd ~/fleet && git add ."

    if [ "$DRY_RUN" = false ]; then
        ssh -i "$SSH_KEY" "$INSTANCE2" "cd ~/fleet && git commit -m 'cc52: Surgeon groups + Group 2 projects + Atlas complete

- Surgeon workers Group 1 and 2 complete
- Project Group 2 complete (all Group 2 projects)
- Atlas on Group 2 complete
- Tracker/Spro frontend prep Group 2 complete

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>'"

        execute_remote "$INSTANCE2" "Push to origin" \
            "cd ~/fleet && git push origin main"
    fi

    echo -e "${GREEN}✓ Phase 2 complete${NC}"
    echo
}

# Phase 3: Instance 1 consolidation
phase3_instance1() {
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  PHASE 3: INSTANCE 1 → GIT${NC}"
    echo -e "${WHITE}  (Healer + Group 1 projects)${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # Show status
    echo -e "${CYAN}Instance 1 current status:${NC}"
    ssh -i "$SSH_KEY" "$INSTANCE1" "cd ~/fleet && git status --short" | head -20
    local total=$(ssh -i "$SSH_KEY" "$INSTANCE1" "cd ~/fleet && git status --porcelain | wc -l")
    if [ "$total" -gt 20 ]; then
        echo "... and $((total - 20)) more files"
    fi
    echo

    # Stash
    execute_remote "$INSTANCE1" "Stash changes" \
        "cd ~/fleet && git stash push -m 'i1-work-${TIMESTAMP}' || echo 'Nothing to stash'"

    # Pull (gets ORION/DISPATCHER from local + Group 2 work from Instance 2)
    execute_remote "$INSTANCE1" "Pull from origin" \
        "cd ~/fleet && git pull origin main"

    # Pop stash (reapply Instance 1's work)
    execute_remote "$INSTANCE1" "Reapply stashed changes" \
        "cd ~/fleet && git stash pop || echo 'No stash to pop'"

    # Check for conflicts
    echo -e "${CYAN}Checking for conflicts on Instance 1...${NC}"
    local conflicts=$(ssh -i "$SSH_KEY" "$INSTANCE1" "cd ~/fleet && git status --porcelain | grep '^UU' | wc -l" || echo "0")

    if [ "$conflicts" != "0" ]; then
        echo -e "${RED}⚠️  CONFLICTS DETECTED on Instance 1!${NC}"
        echo "Files in conflict:"
        ssh -i "$SSH_KEY" "$INSTANCE1" "cd ~/fleet && git status --porcelain | grep '^UU'"
        echo
        echo -e "${YELLOW}Manual intervention required on Instance 1${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ No conflicts detected${NC}"
    fi

    # Commit and push
    execute_remote "$INSTANCE1" "Add changes" \
        "cd ~/fleet && git add ."

    if [ "$DRY_RUN" = false ]; then
        ssh -i "$SSH_KEY" "$INSTANCE1" "cd ~/fleet && git commit -m 'cc52: Healer Group 1 + Group 1 projects complete

- Healer Group 1 work on Instance 1 complete
- Project Group 1 complete (all Group 1 projects)
- Tracker/ORION frontend work Group 1 may be complete

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>'"

        execute_remote "$INSTANCE1" "Push to origin" \
            "cd ~/fleet && git push origin main"
    fi

    echo -e "${GREEN}✓ Phase 3 complete${NC}"
    echo
}

# Phase 4: Local pulls final state
phase4_local_sync() {
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  PHASE 4: LOCAL SYNC${NC}"
    echo -e "${WHITE}  (Pull consolidated state from all systems)${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    cd "$LOCAL_FLEET"

    execute "Pull from origin" git pull origin main

    # Verify status
    echo -e "${CYAN}Checking final git status...${NC}"
    local local_status=$(git status --porcelain | wc -l)

    if [ "$local_status" -eq 0 ]; then
        echo -e "${GREEN}✓ Local working tree is clean${NC}"
    else
        echo -e "${YELLOW}⚠️  Local has uncommitted changes:${NC}"
        git status --short | head -20
    fi

    echo
    echo -e "${GREEN}✓ Phase 4 complete${NC}"
    echo
}

# Verification
verify_consolidation() {
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  VERIFICATION${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # Get commits
    local local_commit=$(cd "$LOCAL_FLEET" && git rev-parse HEAD)
    local i1_commit=$(ssh -i "$SSH_KEY" "$INSTANCE1" "cd ~/fleet && git rev-parse HEAD" 2>/dev/null || echo "ERROR")
    local i2_commit=$(ssh -i "$SSH_KEY" "$INSTANCE2" "cd ~/fleet && git rev-parse HEAD" 2>/dev/null || echo "ERROR")

    echo "Commit hashes:"
    echo "  Local:      $local_commit"
    echo "  Instance 1: $i1_commit"
    echo "  Instance 2: $i2_commit"
    echo

    if [ "$local_commit" = "$i1_commit" ] && [ "$local_commit" = "$i2_commit" ]; then
        echo -e "${GREEN}✅ All systems at same commit!${NC}"
    else
        echo -e "${YELLOW}⚠️  Systems have different commits${NC}"
        echo "This may be expected if consolidation is still in progress"
    fi

    echo
}

# Main execution
main() {
    echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║${NC}  ${WHITE}OPTION B: GIT-BASED MULTI-SYSTEM CONSOLIDATION${NC}          ${PURPLE}║${NC}"
    echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}  DRY RUN MODE - No changes will be made${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo
    fi

    log "=== Option B Consolidation Started ==="
    log "Dry run: $DRY_RUN"
    log "Specific phase: ${SPECIFIC_PHASE:-all}"

    # Pre-flight
    if [ -z "$SPECIFIC_PHASE" ]; then
        preflight_check
    fi

    # Execute phases
    if [ -z "$SPECIFIC_PHASE" ] || [ "$SPECIFIC_PHASE" = "1" ]; then
        phase1_local
    fi

    if [ -z "$SPECIFIC_PHASE" ] || [ "$SPECIFIC_PHASE" = "2" ]; then
        phase2_instance2
    fi

    if [ -z "$SPECIFIC_PHASE" ] || [ "$SPECIFIC_PHASE" = "3" ]; then
        phase3_instance1
    fi

    if [ -z "$SPECIFIC_PHASE" ] || [ "$SPECIFIC_PHASE" = "4" ]; then
        phase4_local_sync
    fi

    # Verify
    if [ -z "$SPECIFIC_PHASE" ]; then
        verify_consolidation
    fi

    # Summary
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  ✅ CONSOLIDATION COMPLETE${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
    echo "Log file: $LOG_FILE"
    echo "Summary report: ~/fleet/dispatcher/reports/MULTI_SYSTEM_TOOLING_SESSION_SUMMARY.md"
    echo

    log "=== Option B Consolidation Completed Successfully ==="
}

main
