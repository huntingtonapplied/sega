#!/bin/bash

# FLEET GitLab Bulk Branch Push Script - Branch-based Workflow with Conflict Resolution
# Creates feature branches, fetches/merges remote changes, resolves conflicts, then pushes
# Usage: ./gitlab_bulk_branch_push.sh [commit_number] [instance]
#
# Arguments:
#   commit_number: Branch prefix (e.g., "cc58", "update42")
#   instance: "prod-1", "prod-2", or "local" (defaults to auto-detect)
#
# Examples:
#   ./gitlab_bulk_branch_push.sh cc58 prod-1
#   ./gitlab_bulk_branch_push.sh cc59 local
#
# SAFETY CHECK: This script is designed to run from ~/fleet directory.

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

# Configuration
COMMIT_NUMBER="${1}"
INSTANCE="${2}"
LOG_FILE="/tmp/bulk_branch_push_$(date +%Y%m%d_%H%M%S).log"
BASE_BRANCH="main"
MERGE_STRATEGY="ours"  # On conflict, prefer our changes

# Auto-detect instance if not provided
# Matches hostname against SYSMON_INSTANCE*_IP / INSTANCE*_IP (injected from
# config/sega.toml by the sega CLI); falls back to "local" when unset.
if [ -z "$INSTANCE" ]; then
    HOSTNAME=$(hostname)
    IP1="${SYSMON_INSTANCE1_IP:-${INSTANCE1_IP:-}}"
    IP2="${SYSMON_INSTANCE2_IP:-${INSTANCE2_IP:-}}"
    if [ -n "$IP1" ] && [[ "$HOSTNAME" == *"$IP1"* ]]; then
        INSTANCE="prod-1"
    elif [ -n "$IP2" ] && [[ "$HOSTNAME" == *"$IP2"* ]]; then
        INSTANCE="prod-2"
    else
        INSTANCE="local"
    fi
    echo "Auto-detected instance: $INSTANCE"
fi

# Validate arguments
if [ -z "$COMMIT_NUMBER" ]; then
    echo "ERROR: Commit number required"
    echo "Usage: $0 <commit_number> [instance]"
    echo "Example: $0 cc58 prod-1"
    exit 1
fi

# Generate branch name: {commit_number}-fleet-{instance}
BRANCH_NAME="${COMMIT_NUMBER}-fleet-${INSTANCE}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output and log
print_log() {
    local color=$1
    shift
    echo -e "${color}$*${NC}" | tee -a "$LOG_FILE"
}

# Function to check for git locks
check_git_locks() {
    local path=$1
    local project=$2

    if [ -f "$path/.git/index.lock" ]; then
        print_log "$RED" "   [ERROR] Git index lock found in $project"
        return 1
    fi

    if find "$path/.git/refs" -name "*.lock" -type f 2>/dev/null | grep -q .; then
        print_log "$RED" "   [ERROR] Git refs lock found in $project"
        return 1
    fi

    if [ -f "$path/.git/HEAD.lock" ]; then
        print_log "$RED" "   [ERROR] Git HEAD lock found in $project"
        return 1
    fi

    return 0
}

# Initialize
print_log "$BLUE" "=== FLEET GitLab Bulk Branch Push Operation ==="
print_log "$CYAN" "Branch Name: $BRANCH_NAME"
print_log "$CYAN" "Instance: $INSTANCE"
print_log "$CYAN" "Base Branch: $BASE_BRANCH"
print_log "$BLUE" "Timestamp: $(date)"
print_log "$BLUE" "Log File: $LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Define all projects to process (space-separated; set SYSNC_ALL_PROJECTS,
# e.g. "atlas hermes orion", or configure [instances].projects in
# config/sega.toml and run via the sega CLI)
if [ -z "${SYSNC_ALL_PROJECTS:-}" ]; then
    echo "ERROR: SYSNC_ALL_PROJECTS not set (space-separated project list)." >&2
    echo "Set SYSNC_ALL_PROJECTS or configure [instances].projects in config/sega.toml and run via the sega CLI." >&2
    exit 1
fi
PROJECTS=(${SYSNC_ALL_PROJECTS})

# Define docs submodules
DOCS_MODULES=(
    docs/design docs/operations docs/social docs/healer docs/notes
)

# Track success and failures
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_MODULES=()
SKIPPED_COUNT=0
CONFLICT_COUNT=0

# Function to push a submodule with branch workflow
push_submodule_branch() {
    local project=$1
    local path=$2
    local had_stash=false
    local had_conflicts=false

    print_log "$BLUE" "Processing $project..."

    # Check if directory exists
    if [ ! -d "$path" ]; then
        print_log "$YELLOW" "   [SKIP] Directory $path not found"
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

    # Check if it's a git repository
    if [ ! -e ".git" ]; then
        print_log "$YELLOW" "   [SKIP] Not a git repository"
        cd - > /dev/null
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        return
    fi

    # Check for git locks
    if ! check_git_locks "$path" "$project"; then
        print_log "$RED" "   [ERROR] Git locks detected, skipping"
        cd - > /dev/null
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_MODULES+=("$project (git locks)")
        return
    fi

    # Get current branch
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
    if [ -z "$CURRENT_BRANCH" ]; then
        CURRENT_BRANCH="$BASE_BRANCH"
    fi
    print_log "$NC" "   Current branch: $CURRENT_BRANCH"

    # Stash any uncommitted changes (safety measure)
    if git diff --quiet && git diff --cached --quiet; then
        print_log "$NC" "   [INFO] No uncommitted changes to stash"
    else
        print_log "$CYAN" "   [STASH] Stashing uncommitted changes for safety..."
        if git stash push -u -m "Bulk branch push safety stash - $BRANCH_NAME" 2>&1 | tee -a "$LOG_FILE"; then
            had_stash=true
            print_log "$GREEN" "   [OK] Changes stashed"
        else
            print_log "$RED" "   [ERROR] Failed to stash changes"
            cd - > /dev/null
            FAILED_COUNT=$((FAILED_COUNT + 1))
            FAILED_MODULES+=("$project (stash failed)")
            return
        fi
    fi

    # Fetch remote changes
    print_log "$CYAN" "   [FETCH] Fetching from origin..."
    if git fetch origin 2>&1 | tee -a "$LOG_FILE"; then
        print_log "$GREEN" "   [OK] Fetch successful"
    else
        print_log "$YELLOW" "   [WARNING] Fetch failed, continuing anyway"
    fi

    # Check if remote branch exists
    if git ls-remote --exit-code --heads origin "$BASE_BRANCH" >/dev/null 2>&1; then
        print_log "$NC" "   [INFO] Remote $BASE_BRANCH exists"

        # Create and checkout new branch from current state
        print_log "$CYAN" "   [BRANCH] Creating branch: $BRANCH_NAME"
        if git checkout -b "$BRANCH_NAME" 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [OK] Branch created"
        else
            # Branch might already exist, try to switch to it
            print_log "$YELLOW" "   [INFO] Branch exists, switching to it"
            if ! git checkout "$BRANCH_NAME" 2>&1 | tee -a "$LOG_FILE"; then
                print_log "$RED" "   [ERROR] Cannot checkout branch"
                if [ "$had_stash" = true ]; then
                    git stash pop 2>&1 | tee -a "$LOG_FILE"
                fi
                cd - > /dev/null
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_MODULES+=("$project (checkout failed)")
                return
            fi
        fi

        # Merge origin/main into our branch
        print_log "$CYAN" "   [MERGE] Merging origin/$BASE_BRANCH into $BRANCH_NAME..."
        if git merge "origin/$BASE_BRANCH" -X "$MERGE_STRATEGY" -m "Merge origin/$BASE_BRANCH into $BRANCH_NAME" 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [OK] Merge successful"
        else
            # Check if there are conflicts
            if git diff --name-only --diff-filter=U | grep -q .; then
                had_conflicts=true
                CONFLICT_COUNT=$((CONFLICT_COUNT + 1))
                print_log "$YELLOW" "   [CONFLICT] Merge conflicts detected, resolving with strategy: $MERGE_STRATEGY"

                # Resolve conflicts by accepting our version
                git checkout --ours . 2>&1 | tee -a "$LOG_FILE"
                git add -A 2>&1 | tee -a "$LOG_FILE"

                if git commit --no-edit 2>&1 | tee -a "$LOG_FILE"; then
                    print_log "$GREEN" "   [OK] Conflicts resolved, merge completed"
                else
                    print_log "$RED" "   [ERROR] Failed to complete merge"
                    if [ "$had_stash" = true ]; then
                        git stash pop 2>&1 | tee -a "$LOG_FILE"
                    fi
                    cd - > /dev/null
                    FAILED_COUNT=$((FAILED_COUNT + 1))
                    FAILED_MODULES+=("$project (merge failed)")
                    return
                fi
            else
                print_log "$YELLOW" "   [WARNING] Merge reported issues but no conflicts found"
            fi
        fi
    else
        print_log "$YELLOW" "   [INFO] Remote $BASE_BRANCH doesn't exist, creating branch from current state"
        if ! git checkout -b "$BRANCH_NAME" 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$RED" "   [ERROR] Failed to create branch"
            if [ "$had_stash" = true ]; then
                git stash pop 2>&1 | tee -a "$LOG_FILE"
            fi
            cd - > /dev/null
            FAILED_COUNT=$((FAILED_COUNT + 1))
            FAILED_MODULES+=("$project (branch creation failed)")
            return
        fi
    fi

    # Pop stash if we had one
    if [ "$had_stash" = true ]; then
        print_log "$CYAN" "   [STASH] Restoring stashed changes..."
        if git stash pop 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [OK] Stash restored"
        else
            print_log "$YELLOW" "   [WARNING] Stash pop had issues, changes might be in stash"
        fi
    fi

    # Check for changes to commit
    STATUS_OUTPUT=$(git status --porcelain 2>/dev/null || echo "")
    if [[ -n "$STATUS_OUTPUT" ]]; then
        print_log "$NC" "   Found changes, staging and committing..."

        if git add -A 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [OK] Changes staged"
        else
            print_log "$RED" "   [ERROR] Failed to stage changes"
        fi

        COMMIT_MSG="$COMMIT_NUMBER - Updates from $INSTANCE"
        if git commit -m "$COMMIT_MSG" 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [OK] Commit successful"
        else
            print_log "$YELLOW" "   [INFO] Commit failed or no changes"
        fi
    else
        print_log "$NC" "   [INFO] No changes to commit"
    fi

    # Push branch to remote
    print_log "$CYAN" "   [PUSH] Pushing branch $BRANCH_NAME to origin..."
    if git push -u origin "$BRANCH_NAME" 2>&1 | tee -a "$LOG_FILE"; then
        if [ "$had_conflicts" = true ]; then
            print_log "$GREEN" "   [SUCCESS] $project pushed (with conflict resolution)"
        else
            print_log "$GREEN" "   [SUCCESS] $project pushed"
        fi
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        print_log "$RED" "   [FAILED] Push failed for $project"
        FAILED_COUNT=$((FAILED_COUNT + 1))
        FAILED_MODULES+=("$project (push failed)")
    fi

    # Return to previous directory
    cd - > /dev/null
    echo "" | tee -a "$LOG_FILE"
}

# Main execution
print_log "$BLUE" "Phase 1: Processing FLEET Project Submodules..."
print_log "$BLUE" "================================================"

for project in "${PROJECTS[@]}"; do
    push_submodule_branch "$project" "$project"
done

print_log "$BLUE" "Phase 2: Processing Documentation Submodules..."
print_log "$BLUE" "==================================================="

for module in "${DOCS_MODULES[@]}"; do
    project_name=$(basename "$module")
    push_submodule_branch "docs/$project_name" "$module"
done

print_log "$BLUE" "Phase 3: Processing Main FLEET Repository..."
print_log "$BLUE" "============================================="

# Process main repository with branch workflow
push_submodule_branch "main repository" "."

# Print summary
echo "" | tee -a "$LOG_FILE"
print_log "$BLUE" "=================================================="
print_log "$BLUE" "FLEET GitLab Bulk Branch Push Summary"
print_log "$BLUE" "=================================================="
print_log "$CYAN" "Branch Name: $BRANCH_NAME"
print_log "$GREEN" "Successful: $SUCCESS_COUNT"
print_log "$RED" "Failed: $FAILED_COUNT"
print_log "$YELLOW" "Skipped: $SKIPPED_COUNT"
print_log "$YELLOW" "Conflicts Resolved: $CONFLICT_COUNT"

# List failed modules if any
if [ ${#FAILED_MODULES[@]} -gt 0 ]; then
    echo "" | tee -a "$LOG_FILE"
    print_log "$RED" "Failed modules:"
    for module in "${FAILED_MODULES[@]}"; do
        print_log "$RED" "  - $module"
    done
fi

# Next steps
echo "" | tee -a "$LOG_FILE"
print_log "$CYAN" "=================================================="
print_log "$CYAN" "Next Steps:"
print_log "$CYAN" "=================================================="
print_log "$NC" "1. Review branches on GitLab"
print_log "$NC" "2. Create merge requests for $BRANCH_NAME branches"
print_log "$NC" "3. Review and merge into main"
print_log "$NC" ""
print_log "$NC" "Or auto-merge with:"
print_log "$GREEN" "  git checkout main && git merge $BRANCH_NAME && git push origin main"

# Final status
echo "" | tee -a "$LOG_FILE"
print_log "$BLUE" "Timestamp: $(date)"
print_log "$BLUE" "Full log saved to: $LOG_FILE"

if [ $FAILED_COUNT -eq 0 ]; then
    print_log "$GREEN" "[COMPLETE] All operations completed successfully!"
    exit 0
else
    print_log "$YELLOW" "[WARNING] Some operations failed. Check log for details."
    exit 1
fi
