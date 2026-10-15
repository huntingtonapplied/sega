#!/bin/bash

# FLEET GitLab Bulk Push Script - Complete Version
# Pushes all submodules and main repository to GitLab with proper logging and error handling
# Usage: ./gitlab_bulk_push.sh [commit_message]
#
# SAFETY CHECK: This script is designed to run from ~/fleet directory.
# Current execution directory will be verified before proceeding.

set -e
set -o pipefail  # Ensure pipeline failures are caught (fixes: git push | tee reporting success on push failure)

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
COMMIT_MSG="${1:-Ecosystem update - documentation integration and standards compliance}"
LOG_FILE="/tmp/bulk_push_$(date +%Y%m%d_%H%M%S).log"
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
print_log "$BLUE" "=== FLEET GitLab Bulk Push Operation ==="
print_log "$BLUE" "Commit Message: $COMMIT_MSG"
print_log "$BLUE" "Timestamp: $(date)"
print_log "$BLUE" "Log File: $LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Define all FLEET projects (only actual submodules - orion and atlas are not submodules yet)
PROJECTS=(
    orion atlas hermes hermes scanner_app
    atlas atlas hermes atlas atlas
    orion hermes atlas hermes sega vega telemetry atlas
)

# Define docs submodules - these ARE actual git submodules
DOCS_MODULES=(
    docs/design docs/operations docs/social docs/healer docs/notes
)

# Track success and failures
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_MODULES=()
SKIPPED_COUNT=0

# Function to push a submodule
push_submodule() {
    local project=$1
    local path=$2
    local changes_found=false
    local push_success=false
    
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
    
    # Get current branch (handle detached HEAD state)
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
    if [ -z "$CURRENT_BRANCH" ]; then
        # Detached HEAD state - we need to be on a branch to push
        # Check if main branch exists, if so checkout (preserving changes)
        if git show-ref --verify --quiet refs/heads/main; then
            CURRENT_BRANCH="main"
            print_log "$YELLOW" "   [INFO] Detached HEAD detected, checking out main branch (preserving changes)"
            git checkout main 2>&1 | tee -a "$LOG_FILE" || {
                print_log "$RED" "   [ERROR] Failed to checkout main"
                cd - > /dev/null
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_MODULES+=("$project (checkout failed)")
                return
            }
        else
            # main doesn't exist, create it from current HEAD
            CURRENT_BRANCH="main"
            print_log "$YELLOW" "   [INFO] Creating main branch from current HEAD"
            git checkout -b main 2>&1 | tee -a "$LOG_FILE" || {
                print_log "$RED" "   [ERROR] Failed to create main branch"
                cd - > /dev/null
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_MODULES+=("$project (branch creation failed)")
                return
            }
        fi
    fi
    print_log "$NC" "   Branch: $CURRENT_BRANCH"
    
    # Check for changes
    STATUS_OUTPUT=$(git status --porcelain 2>/dev/null || echo "")
    if [[ -n "$STATUS_OUTPUT" ]]; then
        changes_found=true
        print_log "$NC" "   Found changes, staging and committing..."
        
        # Stage all changes
        if git add -A 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [OK] Changes staged"
        else
            print_log "$RED" "   [ERROR] Failed to stage changes"
        fi
        
        # Commit changes
        if git commit -m "$COMMIT_MSG" 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [OK] Commit successful"
        else
            print_log "$YELLOW" "   [INFO] No changes to commit or commit failed"
        fi
    else
        print_log "$NC" "   [INFO] No changes to stage"
    fi
    
    # Check for unpushed commits
    UNPUSHED=$(git log origin/${CURRENT_BRANCH}..HEAD 2>/dev/null | wc -l || echo "0")
    if [ "$UNPUSHED" -gt 0 ] || [ "$changes_found" = true ]; then
        print_log "$NC" "   Pushing to remote..."
        
        # Try to push to current branch
        if git push origin "$CURRENT_BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [SUCCESS] $project pushed successfully to $CURRENT_BRANCH"
            push_success=true
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        # Try fallback branch if main fails
        elif [ "$CURRENT_BRANCH" != "$FALLBACK_BRANCH" ] && git push origin "$FALLBACK_BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
            print_log "$GREEN" "   [SUCCESS] $project pushed successfully to $FALLBACK_BRANCH"
            push_success=true
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            print_log "$RED" "   [FAILED] Push failed for $project"
            FAILED_COUNT=$((FAILED_COUNT + 1))
            FAILED_MODULES+=("$project (push failed)")
        fi
    else
        print_log "$NC" "   [INFO] Nothing to push"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    fi
    
    # Return to previous directory
    cd - > /dev/null
    echo "" | tee -a "$LOG_FILE"
}

# Main execution
print_log "$BLUE" "Phase 1: Processing FLEET Project Submodules..."
print_log "$BLUE" "================================================"

# Process main project submodules
for project in "${PROJECTS[@]}"; do
    push_submodule "$project" "$project"
done

print_log "$BLUE" "Phase 2: Processing Documentation Submodules..."
print_log "$BLUE" "==================================================="

# Process docs submodules
for module in "${DOCS_MODULES[@]}"; do
    project_name=$(basename "$module")
    push_submodule "docs/$project_name" "$module"
done

print_log "$BLUE" "Phase 3: Processing Main FLEET Repository..."
print_log "$BLUE" "============================================="

# Save current directory
MAIN_REPO_DIR=$(pwd)

# Check for git locks in main repository
if ! check_git_locks "." "main repository"; then
    print_log "$RED" "[ERROR] Git locks detected in main repository, aborting"
    exit 1
fi

# Check main repository status
STATUS_OUTPUT=$(git status --porcelain 2>/dev/null || echo "")
if [[ -n "$STATUS_OUTPUT" ]]; then
    print_log "$NC" "Found changes in main repository, staging and committing..."
    
    # Stage all changes
    if git add -A 2>&1 | tee -a "$LOG_FILE"; then
        print_log "$GREEN" "[OK] Changes staged"
    else
        print_log "$RED" "[ERROR] Failed to stage changes"
    fi
    
    # Commit changes
    if git commit -m "$COMMIT_MSG" 2>&1 | tee -a "$LOG_FILE"; then
        print_log "$GREEN" "[OK] Main repository commit successful"
    else
        print_log "$YELLOW" "[WARNING] Main repository commit failed or no changes"
    fi
else
    print_log "$NC" "[INFO] No changes in main repository to stage"
fi

# Push main repository
print_log "$NC" "Pushing main repository..."
if git push origin "$MAIN_BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
    print_log "$GREEN" "[SUCCESS] Main FLEET repository pushed successfully"
else
    print_log "$RED" "[FAILED] Main repository push failed"
    FAILED_COUNT=$((FAILED_COUNT + 1))
    FAILED_MODULES+=("main repository")
fi

# Print summary
echo "" | tee -a "$LOG_FILE"
print_log "$BLUE" "="
print_log "$BLUE" "FLEET GitLab Bulk Push Summary"
print_log "$BLUE" "="
print_log "$GREEN" "Successful: $SUCCESS_COUNT"
print_log "$RED" "Failed: $FAILED_COUNT"
print_log "$YELLOW" "Skipped: $SKIPPED_COUNT"

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
if [ $FAILED_COUNT -eq 0 ]; then
    print_log "$GREEN" "[COMPLETE] All operations completed successfully!"
    exit 0
else
    print_log "$YELLOW" "[WARNING] Some operations failed. Check log for details."
    exit 1
fi