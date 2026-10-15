#!/bin/bash

# FLEET GitLab Bulk Pull Script - Optimized Version
# Pulls all submodules and main repository from GitLab with proper logging and error handling
# Usage: ./gitlab_bulk_pull.sh [--dry-run]
#
# SAFETY CHECK: This script is designed to run from /home/testuser/fleet directory only.
# Current execution directory will be verified before proceeding.

set -e

# Safety check - verify we're in the correct directory
EXPECTED_DIR="$HOME/fleet"
CURRENT_DIR=$(pwd)
if [ "$CURRENT_DIR" != "$EXPECTED_DIR" ]; then
    echo "ERROR: Script must be run from $EXPECTED_DIR"
    echo "Current directory: $CURRENT_DIR"
    exit 1
fi

echo "✓ Safety check passed: Running from correct directory ($CURRENT_DIR)"

# Parse arguments
DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "✓ DRY RUN MODE - No changes will be made"
fi

# Configuration
LOG_FILE="/tmp/bulk_pull_$(date +%Y%m%d_%H%M%S).log"
MAIN_BRANCH="main"
FALLBACK_BRANCH="master"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output and log
print_log() {
    local color=$1
    shift
    echo -e "${color}$*${NC}" | tee -a "$LOG_FILE"
}

# SAFETY GUARD 2026-07-03: returns 0 (true) if CWD git repo has unmerged
# detached/branch work (commits ahead of origin/main) → must be left untouched.
guard_should_skip() {
    git fetch origin main -q 2>/dev/null || true
    local cur ahead
    cur=$(git branch --show-current 2>/dev/null)
    ahead=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
    if { [ -z "$cur" ] || [ "$cur" != "main" ]; } && [ "${ahead:-0}" -gt 0 ] 2>/dev/null; then
        GUARD_REASON="${cur:-detached HEAD} has ${ahead} commit(s) ahead of origin/main"
        return 0
    fi
    return 1
}

# Function to check for git locks
check_git_locks() {
    local path=$1
    local project=$2

    # Check for index.lock
    if [ -f "$path/.git/index.lock" ]; then
        print_log "$RED" "   [ERROR] Git index lock found in $project (.git/index.lock)"
        return 1
    fi

    # Check for refs locks
    if find "$path/.git/refs" -name "*.lock" -type f 2>/dev/null | grep -q .; then
        print_log "$RED" "   [ERROR] Git refs lock found in $project"
        return 1
    fi

    # Check for HEAD.lock
    if [ -f "$path/.git/HEAD.lock" ]; then
        print_log "$RED" "   [ERROR] Git HEAD lock found in $project (.git/HEAD.lock)"
        return 1
    fi

    return 0
}

# Initialize
print_log "$BLUE" "=== FLEET GitLab Bulk Pull Operation ==="
print_log "$BLUE" "Timestamp: $(date)"
print_log "$BLUE" "Log File: $LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Define all FLEET projects (submodules only - part of main repo handled separately)
PROJECTS=(
    orion atlas hermes hermes scanner_app
    atlas atlas hermes atlas atlas
    orion hermes atlas hermes sega vega telemetry
)
# Note: orion, atlas, atlas, swarm are part of main repo - no separate pull needed

# Define docs submodules - these ARE actual git submodules
DOCS_MODULES=(
    docs/design docs/operations docs/social docs/healer docs/notes
)

# Track success and failures
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_MODULES=()
SKIPPED_COUNT=0
STASHED_REPOS=()
STASH_RESTORE_FAILED=()

# Function to pull a submodule
pull_submodule() {
    local project=$1
    local path=$2
    local pull_success=false
    local had_stash=false

    print_log "$BLUE" "Processing $project..."

    # Check if directory exists
    if [ ! -d "$path" ]; then
        print_log "$YELLOW" "   [SKIP] Directory $path not found, skipping"
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        return
    fi

    # Enter directory
    cd "$path" 2>/dev/null || {
        print_log "$RED" "   [ERROR] Cannot enter directory $path"
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_MODULES+=("$project (cannot access)")
        return
    }

    # Check if it's a git repository (submodules have .git file or directory)
    if [ ! -e ".git" ]; then
        print_log "$YELLOW" "   [SKIP] Not a git repository, skipping"
        cd - > /dev/null
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        return
    fi

    # Check for git locks
    if ! check_git_locks "$path" "$project"; then
        print_log "$RED" "   [ERROR] Git locks detected, skipping $project"
        cd - > /dev/null
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_MODULES+=("$project (git locks)")
        return
    fi

    # Get current branch
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
    print_log "$NC" "   Branch: $CURRENT_BRANCH"

    # SAFETY GUARD: never stash/pull a submodule with unmerged detached/branch work
    if [ "$DRY_RUN" = false ] && guard_should_skip; then
        print_log "$RED" "   🛑 SKIP $project: ${GUARD_REASON} — left untouched (protects active branch work)."
        cd - > /dev/null
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        return
    fi

    # Check for uncommitted changes
    STATUS_OUTPUT=$(git status --porcelain 2>/dev/null || echo "")
    if [[ -n "$STATUS_OUTPUT" ]]; then
        had_stash=true
        STASHED_REPOS+=("$project")
        if [ "$DRY_RUN" = true ]; then
            print_log "$YELLOW" "   [DRY-RUN] Would stash uncommitted changes"
        else
            print_log "$YELLOW" "   [WARNING] Uncommitted changes detected, stashing..."
            if git stash save "Auto-stash before bulk pull $(date)" 2>&1 | tee -a "$LOG_FILE"; then
                print_log "$GREEN" "   [OK] Changes stashed"
            else
                print_log "$RED" "   [ERROR] Failed to stash changes"
                cd - > /dev/null
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_MODULES+=("$project (stash failed)")
                return
            fi
        fi
    fi

    # Pull from remote
    if [ "$DRY_RUN" = true ]; then
        print_log "$NC" "   [DRY-RUN] Would pull from remote"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        print_log "$NC" "   Pulling from remote..."
        if git pull origin "$CURRENT_BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [SUCCESS] $project pulled successfully from $CURRENT_BRANCH"
            pull_success=true
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        # Try fallback branch if main fails
        elif [ "$CURRENT_BRANCH" != "$FALLBACK_BRANCH" ] && git pull origin "$FALLBACK_BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [SUCCESS] $project pulled successfully from $FALLBACK_BRANCH"
            pull_success=true
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            print_log "$RED" "   [FAILED] Pull failed for $project"
            FAILED_COUNT=$((FAILED_COUNT + 1))
            FAILED_MODULES+=("$project (pull failed)")
        fi
    fi

    # Restore stash if we created one and pull succeeded
    if [ "$had_stash" = true ] && [ "$pull_success" = true ] && [ "$DRY_RUN" = false ]; then
        print_log "$NC" "   Restoring stashed changes..."
        if git stash pop 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [OK] Stash restored successfully"
        else
            print_log "$YELLOW" "   [WARNING] Stash restore had conflicts - run 'git stash pop' manually in $project"
            STASH_RESTORE_FAILED+=("$project")
        fi
    fi

    # Return to previous directory
    cd - > /dev/null
    echo "" | tee -a "$LOG_FILE"
}

# Main execution
print_log "$BLUE" "Phase 1: Processing Main FLEET Repository..."
print_log "$BLUE" "============================================="

# Save current directory
MAIN_REPO_DIR=$(pwd)
MAIN_HAD_STASH=false

# Check for git locks in main repository
if ! check_git_locks "." "main repository"; then
    print_log "$RED" "[ERROR] Git locks detected in main repository, aborting"
    exit 1
fi

# Check main repository for uncommitted changes
STATUS_OUTPUT=$(git status --porcelain 2>/dev/null || echo "")
if [[ -n "$STATUS_OUTPUT" ]]; then
    MAIN_HAD_STASH=true
    STASHED_REPOS+=("main repository")
    if [ "$DRY_RUN" = true ]; then
        print_log "$YELLOW" "[DRY-RUN] Would stash uncommitted changes in main repository"
    else
        print_log "$YELLOW" "[WARNING] Uncommitted changes detected in main repository, stashing..."
        if git stash save "Auto-stash before bulk pull $(date)" 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "[OK] Changes stashed"
        else
            print_log "$RED" "[ERROR] Failed to stash changes"
            exit 1
        fi
    fi
fi

# Pull main repository
if [ "$DRY_RUN" = true ]; then
    print_log "$NC" "[DRY-RUN] Would pull main repository"
else
    print_log "$NC" "Pulling main repository..."
    if git pull origin "$MAIN_BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
        print_log "$GREEN" "[SUCCESS] Main FLEET repository pulled successfully"
    else
        print_log "$RED" "[FAILED] Main repository pull failed"
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_MODULES+=("main repository")
    fi
fi

# Sync submodules after pulling main repo - pull latest from remote for all
# SAFETY GUARD: per-submodule; skip any on a detached HEAD or non-main branch
# with commits ahead of origin/main (a bare 'git pull origin main' there would
# merge main INTO the active branch — never do that).
if [ "$DRY_RUN" = true ]; then
    print_log "$NC" "[DRY-RUN] Would pull latest for all submodules"
else
    print_log "$NC" "Pulling latest from remote for all submodules (guarded)..."
    while IFS= read -r _sm; do
        _smp=$(echo "$_sm" | awk '{print $2}')
        [ -n "$_smp" ] && [ -d "$_smp" ] || continue
        ( cd "$_smp" || exit 0
          if guard_should_skip; then
              print_log "$RED" "   🛑 SKIP $_smp: ${GUARD_REASON} — not pulling main into its branch."
          else
              git pull origin main 2>&1 | tee -a "$LOG_FILE" >/dev/null && print_log "$GREEN" "   [OK] $_smp" || print_log "$YELLOW" "   [WARN] $_smp pull issue"
          fi )
    done < <(git submodule status)
    print_log "$GREEN" "[SUCCESS] Submodule pull sweep complete (guarded)"
fi

# Restore stash if we created one
if [ "$MAIN_HAD_STASH" = true ] && [ "$DRY_RUN" = false ]; then
    print_log "$NC" "Restoring stashed changes in main repository..."
    if git stash pop 2>&1 | tee -a "$LOG_FILE"; then
        print_log "$GREEN" "[OK] Stash restored successfully"
    else
        print_log "$YELLOW" "[WARNING] Stash restore had conflicts - run 'git stash pop' manually in main repository"
        STASH_RESTORE_FAILED+=("main repository")
    fi
fi

echo "" | tee -a "$LOG_FILE"

print_log "$BLUE" "Phase 2: Processing FLEET Project Submodules..."
print_log "$BLUE" "================================================"

# Process main project submodules
for project in "${PROJECTS[@]}"; do
    pull_submodule "$project" "$project"
done

print_log "$BLUE" "Phase 3: Processing Documentation Submodules..."
print_log "$BLUE" "==================================================="

# Process docs submodules
for module in "${DOCS_MODULES[@]}"; do
    project_name=$(basename "$module")
    pull_submodule "docs/$project_name" "$module"
done

# Print summary
echo "" | tee -a "$LOG_FILE"
print_log "$BLUE" "=========================================="
print_log "$BLUE" "FLEET GitLab Bulk Pull Summary"
print_log "$BLUE" "=========================================="
print_log "$GREEN" "Successful: $SUCCESS_COUNT"
print_log "$RED" "Failed: $FAILED_COUNT"
print_log "$YELLOW" "Skipped: $SKIPPED_COUNT"

# List stashed repositories
if [ ${#STASHED_REPOS[@]} -gt 0 ]; then
    echo "" | tee -a "$LOG_FILE"
    print_log "$YELLOW" "Repositories with stashed changes: ${#STASHED_REPOS[@]}"
    for repo in "${STASHED_REPOS[@]}"; do
        print_log "$YELLOW" "  - $repo"
    done
fi

# List stash restore failures
if [ ${#STASH_RESTORE_FAILED[@]} -gt 0 ]; then
    echo "" | tee -a "$LOG_FILE"
    print_log "$RED" "⚠ Stash restore conflicts (manual intervention required):"
    for repo in "${STASH_RESTORE_FAILED[@]}"; do
        print_log "$RED" "  - $repo (run 'cd $repo && git stash pop' to resolve)"
    done
fi

# List failed modules if any
if [ ${#FAILED_MODULES[@]} -gt 0 ]; then
    echo "" | tee -a "$LOG_FILE"
    print_log "$RED" "Failed modules:"
    for module in "${FAILED_MODULES[@]}"; do
        print_log "$RED" "  - $module"
    done
fi

# Final status
echo "" | tee -a "$LOG_FILE"
print_log "$BLUE" "Timestamp: $(date)"
print_log "$BLUE" "Full log saved to: $LOG_FILE"

# Return appropriate exit code
if [ $FAILED_COUNT -eq 0 ] && [ ${#STASH_RESTORE_FAILED[@]} -eq 0 ]; then
    print_log "$GREEN" "[COMPLETE] All operations completed successfully!"
    exit 0
elif [ ${#STASH_RESTORE_FAILED[@]} -gt 0 ]; then
    print_log "$YELLOW" "[WARNING] Pull succeeded but some stashes need manual restoration."
    exit 1
else
    print_log "$YELLOW" "[WARNING] Some operations failed. Check log for details."
    exit 1
fi
