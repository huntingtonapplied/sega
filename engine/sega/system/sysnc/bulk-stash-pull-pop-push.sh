#!/bin/bash
# ============================================================================
# Consolidate This System
# ============================================================================
# PURPOSE:
#   Run this script ON EACH SYSTEM in order to consolidate git changes.
#   Handles submodules first, then parent module.
#
# EXECUTION ORDER:
#   1. Run on Instance 2 first: ssh to i2, run script
#   2. Run on Instance 1 second: ssh to i1, run script (pulls i2's work)
#   3. Run on Local last: run script locally (pulls all distributed work)
#
# USAGE:
#   ./consolidate-this-system.sh [--dry-run] [--commit-number <num>]
#
# OPTIONS:
#   --dry-run           Show what would be done without making changes
#   --commit-number N   Use ccN for commits (auto-increments AFTER pull if omitted)
#
# WHAT IT DOES:
#   0. Safety stash main repo (before touching submodules)
#   1. For each submodule with changes:
#      - Stash → Pull → Detect next commit# → Pop → Commit → Push
#   2. Stash main repo again (captures updated submodule pointers)
#   3. For parent module:
#      - Pull → Pop → Commit → Push
#
# NOTE: Commit number is determined AFTER pull to avoid conflicts when
#       multiple systems push between executions.
# NOTE: Double-stash pattern ensures main repo captures updated submodule
#       pointers after all submodules are processed.
# ============================================================================
#
# ⚠️  READ BEFORE RUNNING — HARD-WON WARNINGS (2026-07)
# ----------------------------------------------------------------------------
# 1. DO NOT RUN OVER A HOST WITH ACTIVE UNCOMMITTED WORK.
#    Step-2 does `git add . && git stash push` on the PARENT, sweeping up EVERY
#    dirty working-tree file — including a live operator's in-progress WIP under
#    parent subdirs (e.g. swarm/). Step-3 is meant to pop it back, but if the
#    script DIES before the pop (classic cause: `fatal: Need to specify how to
#    reconcile divergent branches` when the parent has diverged), that stash is
#    left UNPOPPED. If you then finish the merge/commit MANUALLY, it's easy to
#    forget — the parent ends up clean + 0/0 + submodules synced, so it LOOKS
#    done, but the operator's dirty files are stranded in a
#    `main-post-submodule-update-<ts>` stash. Work is preserved, but their
#    working tree is silently missing their in-progress files.
#
# 2. MANDATORY POST-RUN CHECK (every host, even after a manual finish):
#       git stash list | grep -E 'main-post-submodule-update|pre-consolidation'
#    If a SAME-DAY stash exists and the run is "done," it was NOT popped →
#    an operator's WIP is stranded. Restore it before declaring success.
#    Verifying commit/push (0/0, synced) is NOT enough — this script mutates
#    the WORKING TREE (stash) separately from commits; verify BOTH.
#
# 3. SAFE STASH RESTORE (live operator may be editing — never blind `git stash pop`):
#    a. `git stash show stash@{0} --name-only`  — list stranded files.
#    b. Classify each vs current tree: MISSING (`! -e f`) = safe pure restore;
#       IDENTICAL (`git rev-parse stash@{0}:f` == `git hash-object f`) = skip;
#       DIFFERS + `git status` shows MODIFIED = operator's LIVE edit, DO NOT touch;
#       DIFFERS + not-modified = edits only in stash, safe to restore.
#    c. `cp` backup anything you'll overwrite (never-lose).
#    d. Restore ONLY the safe set: `git checkout stash@{0} -- <f1> <f2> ...`
#       (this RESTORES from the stash; skip any file the operator is live-editing).
#    e. Verify each: `git rev-parse stash@{0}:f` == `git hash-object f`.
#    f. NEVER drop the stash — it may also hold OTHER operators' parallel work.
#
# 4. SUBMODULE GUARD (see guard_should_skip below): submodules on a detached
#    HEAD or non-main branch AHEAD of origin/main are SKIPPED (never checked out
#    to main) to protect active feature-branch work. The parent pointer for a
#    skipped submodule still needs manual resolution to `origin/main:<sub>`.
# ============================================================================

set -euo pipefail

# Error handler
error_handler() {
    local line_no=$1
    echo -e "\033[0;31m❌ ERROR on line $line_no\033[0m" >&2
    echo -e "\033[0;31m   Command: ${BASH_COMMAND}\033[0m" >&2
    echo -e "\033[0;31m   Exit code: $?\033[0m" >&2
    exit 1
}

trap 'error_handler $LINENO' ERR

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# Parse arguments
DRY_RUN=false
COMMIT_NUMBER=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --commit-number)
            COMMIT_NUMBER="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--commit-number <num>]"
            exit 2
            ;;
    esac
done

FLEET_DIR="${FLEET_DIR:-$HOME/fleet}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# SAFETY GUARD 2026-07-03: submodules skipped because they carry unmerged work
# (on a detached HEAD or non-main branch with commits ahead of origin/main).
# These are NEVER checked-out-to-main / stashed / had-their-pointer-committed,
# to protect active feature-branch work (e.g. an active feature-branch campaign).
SKIPPED_SUBMODULES=""
# Returns 0 (true) if the CWD git repo has unmerged detached/branch work → must skip.
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

# Store whether user provided a commit number
USER_PROVIDED_COMMIT_NUMBER=false
if [ -n "$COMMIT_NUMBER" ]; then
    USER_PROVIDED_COMMIT_NUMBER=true
    # Ensure commit number has 'cc' prefix
    if [[ ! "$COMMIT_NUMBER" =~ ^cc ]]; then
        COMMIT_NUMBER="cc${COMMIT_NUMBER}"
    fi
    echo -e "${CYAN}Using provided commit number: $COMMIT_NUMBER${NC}"
fi

# Detect which system we're on
# Instance IPs come from SYSMON_INSTANCE*_IP / INSTANCE*_IP (injected from
# config/sega.toml by the sega CLI); detection falls back to "Local" when unset.
IP1="${SYSMON_INSTANCE1_IP:-${INSTANCE1_IP:-}}"
IP2="${SYSMON_INSTANCE2_IP:-${INSTANCE2_IP:-}}"
SYSTEM_NAME="unknown"
if [ -d "$FLEET_DIR" ]; then
    cd "$FLEET_DIR"
    if [ -n "$IP2" ] && hostname -I 2>/dev/null | grep -q "$IP2"; then
        SYSTEM_NAME="Instance 2 ($IP2)"
    elif [ -n "$IP1" ] && hostname -I 2>/dev/null | grep -q "$IP1"; then
        SYSTEM_NAME="Instance 1 ($IP1)"
    else
        SYSTEM_NAME="Local"
    fi
fi

echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${PURPLE}║${NC}  ${WHITE}CONSOLIDATE THIS SYSTEM${NC}                                    ${PURPLE}║${NC}"
echo -e "${PURPLE}║${NC}  ${CYAN}System: $SYSTEM_NAME${NC}"
echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}━━━━ DRY RUN MODE ━━━━${NC}"
    echo
fi

# Verify we're in fleet directory
if [ ! -d "$FLEET_DIR" ]; then
    echo -e "${RED}❌ FLEET directory not found: $FLEET_DIR${NC}"
    exit 1
fi

cd "$FLEET_DIR"

# ============================================================================
# DETERMINE COMMIT NUMBER ONCE (for entire consolidation run)
# ============================================================================

if [ "$USER_PROVIDED_COMMIT_NUMBER" = false ] && [ "$DRY_RUN" = false ]; then
    echo -e "${CYAN}Determining commit number for this consolidation run...${NC}"

    # Fetch to see latest remote state without modifying working tree
    git fetch origin main 2>/dev/null || true

    # Get the latest commit number from remote
    LAST_MSG=$(git log origin/main -1 --pretty=%B 2>/dev/null | head -1)
    if [[ "$LAST_MSG" =~ cc([0-9]+) ]]; then
        LAST_NUM="${BASH_REMATCH[1]}"
        COMMIT_NUMBER="cc$((LAST_NUM + 1))"
        echo -e "${GREEN}✓ Will use $COMMIT_NUMBER for all commits (remote is at cc$LAST_NUM)${NC}"
    else
        COMMIT_NUMBER="cc1"
        echo -e "${YELLOW}⚠ Could not detect previous commit number, will use: $COMMIT_NUMBER${NC}"
    fi
    echo
elif [ "$USER_PROVIDED_COMMIT_NUMBER" = false ] && [ "$DRY_RUN" = true ]; then
    COMMIT_NUMBER="ccXX"
    echo -e "${YELLOW}[DRY RUN] Would detect commit number from remote${NC}"
    echo
fi

# Helper: Show command
show_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN]${NC} $*"
    else
        echo -e "${CYAN}▶${NC} $*"
    fi
}

# Helper: Execute command
exec_cmd() {
    if [ "$DRY_RUN" = false ]; then
        "$@"
    fi
}

# Helper: Safe stash push
# Returns 0 if stash was created, 1 if no stash needed
safe_stash_push() {
    local stash_msg="$1"
    if [ "$DRY_RUN" = false ]; then
        # Only stash if there are changes
        if [ -n "$(git status --porcelain)" ]; then
            git stash push -m "$stash_msg"
            return 0  # Stash created
        else
            echo -e "${CYAN}  No changes to stash${NC}"
            return 1  # No stash created
        fi
    fi
    return 0
}

# Helper: Safe stash pop
safe_stash_pop() {
    if [ "$DRY_RUN" = false ]; then
        # Check if there's a stash to pop (git stash show exits 0 if stash exists)
        if git stash show stash@{0} >/dev/null 2>&1; then
            # Try to pop the stash
            if ! git stash pop; then
                echo -e "${RED}⚠️  Stash pop failed - likely conflicts${NC}"
                echo -e "${YELLOW}Checking for conflicts...${NC}"
                # Check for merge conflicts
                if git status --porcelain | grep -q '^UU\|^AA\|^DD'; then
                    echo -e "${RED}❌ Merge conflicts detected after stash pop attempt${NC}"
                    echo -e "${YELLOW}Conflicted files:${NC}"
                    git status --porcelain | grep '^UU\|^AA\|^DD'
                    echo
                    echo -e "${YELLOW}CONFLICT RESOLUTION STEPS (for parent module):${NC}"
                    echo "  1. Resolve content conflicts (script files, etc.)"
                    echo "  2. Update all submodules: git submodule foreach 'git checkout main && git pull origin main'"
                    echo "  3. git add .  # Stage all changes (conflicts resolved + submodule updates)"
                    echo "  4. git commit -m '${COMMIT_NUMBER}'  # Use SAME commit number"
                    echo "  5. git push origin main"
                    echo
                    echo -e "${CYAN}NOTE: Submodule pointer conflicts resolve automatically via submodule update${NC}"
                    echo -e "${CYAN}NOTE: All submodules already processed - do NOT re-run script${NC}"
                    exit 1
                else
                    echo -e "${RED}❌ Stash pop failed for unknown reason${NC}"
                    git status
                    exit 1
                fi
            fi
            return 0
        else
            echo -e "${CYAN}  No stash to pop${NC}"
            return 1
        fi
    fi
    return 0
}

# ============================================================================
# STEP 1: PROCESS SUBMODULES
# ============================================================================

echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${WHITE}  STEP 1: Process Submodules${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# Find submodules with changes
echo -e "${CYAN}Finding submodules with changes...${NC}"

if [ "$DRY_RUN" = false ]; then
    CHANGED_SUBMODULES=$(git submodule foreach --quiet '
        if [ -n "$(git status --porcelain)" ]; then
            echo $sm_path
        fi
    ')

    if [ -z "$CHANGED_SUBMODULES" ]; then
        echo -e "${GREEN}✓ No submodules have changes${NC}"
        echo
    else
        echo -e "${YELLOW}Submodules with changes:${NC}"
        echo "$CHANGED_SUBMODULES" | sed 's/^/  - /'
        echo

        # Process each changed submodule
        while IFS= read -r submodule; do
            if [ -n "$submodule" ]; then
                echo -e "${BLUE}━━━ Processing: $submodule ━━━${NC}"

                cd "$FLEET_DIR/$submodule"

                # SAFETY GUARD: skip submodules with unmerged detached/branch work
                if [ "$DRY_RUN" = false ] && guard_should_skip; then
                    echo -e "${RED}🛑 SKIP $submodule: ${GUARD_REASON} — NOT touched (would orphan active work). Merge manually when ready.${NC}"
                    SKIPPED_SUBMODULES="$SKIPPED_SUBMODULES $submodule"
                    cd "$FLEET_DIR"
                    continue
                fi

                # Show status
                echo -e "${CYAN}Status:${NC}"
                git status --short | head -15 || true
                total=$(git status --porcelain | wc -l)
                if [ "$total" -gt 15 ]; then
                    echo "  ... and $((total - 15)) more files"
                fi
                echo

                # Add all changes (including untracked) before stash
                show_cmd "git add ."
                exec_cmd git add .

                # Stash - track if we created one
                STASH_CREATED=false
                show_cmd "git stash push -m 'pre-consolidation-${TIMESTAMP}'"
                if [ "$DRY_RUN" = false ]; then
                    if safe_stash_push "pre-consolidation-${TIMESTAMP}"; then
                        STASH_CREATED=true
                    fi
                fi

                # Ensure on main branch (after stash, so changes are safe)
                show_cmd "git checkout main"
                if [ "$DRY_RUN" = false ]; then
                    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
                    if [ "$CURRENT_BRANCH" != "main" ]; then
                        echo -e "${YELLOW}  Switching to main branch (currently: ${CURRENT_BRANCH:-detached HEAD})${NC}"
                        git checkout main 2>&1 || {
                            echo -e "${RED}❌ Failed to checkout main branch in $submodule${NC}"
                            exit 1
                        }
                    else
                        echo -e "${CYAN}  Already on main branch${NC}"
                    fi
                fi

                # Pull
                show_cmd "git pull origin main"
                exec_cmd git pull origin main

                # Pop stash - ONLY if we created one during this run
                if [ "$STASH_CREATED" = true ]; then
                    show_cmd "git stash pop"
                    if [ "$DRY_RUN" = false ]; then
                        safe_stash_pop
                    fi
                else
                    echo -e "${CYAN}  Skipping stash pop (no stash created during this run)${NC}"
                fi

                # Check for conflicts
                if [ "$DRY_RUN" = false ]; then
                    if git status --porcelain | grep -q '^UU'; then
                        echo -e "${RED}⚠️  CONFLICTS DETECTED in $submodule!${NC}"
                        git status --porcelain | grep '^UU'
                        echo
                        echo -e "${YELLOW}CONFLICT RESOLUTION STEPS:${NC}"
                        echo "  1. Edit conflicted files to resolve conflicts"
                        echo "  2. git add .  # Stage all changes"
                        echo "  3. git commit -m '${COMMIT_NUMBER}'  # Use SAME commit number"
                        echo "  4. git push origin main"
                        echo "  5. cd \$HOME/fleet  # Return to main repo"
                        echo "  6. Re-run this script: ./docs/scripts/multi-system/bulk-stash-pull-pop-push.sh --commit-number ${COMMIT_NUMBER##cc}"
                        echo
                        echo -e "${CYAN}NOTE: Script will skip already-pushed submodules when re-run${NC}"
                        exit 1
                    fi
                fi

                # Commit
                show_cmd "git add ."
                exec_cmd git add .

                show_cmd "git commit -m '${COMMIT_NUMBER}'"
                if [ "$DRY_RUN" = false ]; then
                    # Check if there's anything to commit
                    if [ -n "$(git status --porcelain)" ]; then
                        git commit -m "${COMMIT_NUMBER}"
                    else
                        echo -e "${CYAN}  No changes to commit${NC}"
                    fi
                fi

                # Push
                show_cmd "git push origin main"
                exec_cmd git push origin main

                echo -e "${GREEN}✓ $submodule complete${NC}"
                echo

                cd "$FLEET_DIR"
            fi
        done <<< "$CHANGED_SUBMODULES"
    fi
else
    echo -e "${YELLOW}[DRY RUN] Would check for changed submodules and process them${NC}"
    echo
fi

# ============================================================================
# STEP 2: STASH MAIN REPO (CAPTURES UPDATED SUBMODULE POINTERS)
# ============================================================================

echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${WHITE}  STEP 2: Stash Main Repo (Captures Updated Submodule Pointers)${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

cd "$FLEET_DIR"

# Add all changes (including untracked and submodule pointer updates) before stash
echo -e "${CYAN}Adding changes before stashing...${NC}"
show_cmd "git add ."
exec_cmd git add .

# SAFETY GUARD: never stage a guarded submodule's pointer (it points to unpushed
# branch work; committing/pushing it would break every other clone).
if [ "$DRY_RUN" = false ]; then
    for _s in $SKIPPED_SUBMODULES; do
        git restore --staged "$_s" 2>/dev/null || true
        echo -e "${YELLOW}  (held back guarded submodule pointer: $_s)${NC}"
    done
fi

echo -e "${CYAN}Stashing main repo with updated submodule pointers...${NC}"
show_cmd "git stash push -m 'main-post-submodule-update-${TIMESTAMP}'"
MAIN_STASH_CREATED=false
if [ "$DRY_RUN" = false ]; then
    # Check if there are any changes (including submodule pointer updates)
    if [ -n "$(git status --porcelain)" ]; then
        safe_stash_push "main-post-submodule-update-${TIMESTAMP}"
        MAIN_STASH_CREATED=true
        echo -e "${GREEN}✓ Main repo stashed with updated submodule pointers${NC}"
    else
        echo -e "${CYAN}✓ No changes in main repo (submodules may not have been pushed yet)${NC}"
    fi
else
    echo -e "${YELLOW}[DRY RUN] Would stash main repo with updated submodule pointers${NC}"
fi
echo

# ============================================================================
# STEP 3: PROCESS PARENT MODULE
# ============================================================================

echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${WHITE}  STEP 3: Process Parent Module${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

cd "$FLEET_DIR"

# Show status before pull
echo -e "${CYAN}Parent module status before pull:${NC}"
if [ "$DRY_RUN" = false ]; then
    git status --short | head -20 || true
    total=$(git status --porcelain | wc -l)
    if [ "$total" -gt 20 ]; then
        echo "  ... and $((total - 20)) more files"
    fi
fi
echo

# Pull
show_cmd "git pull origin main"
exec_cmd git pull origin main

# Pop stash - ONLY if we created one in Step 2
if [ "$MAIN_STASH_CREATED" = true ]; then
    show_cmd "git stash pop"
    if [ "$DRY_RUN" = false ]; then
        safe_stash_pop
    fi
else
    echo -e "${CYAN}  Skipping stash pop (no main stash created)${NC}"
fi

# Update all submodules to latest (not just ones with local changes)
# SAFETY GUARD: per-submodule — skip any on a detached HEAD or non-main branch
# with commits ahead of origin/main (never force checkout main over their work).
echo -e "${CYAN}Updating all submodules to latest remote commits (guarded)...${NC}"
show_cmd "git submodule foreach (guarded checkout main + pull)"
if [ "$DRY_RUN" = false ]; then
    while IFS= read -r _sm; do
        _smp=$(echo "$_sm" | awk '{print $2}')
        [ -n "$_smp" ] && [ -d "$FLEET_DIR/$_smp" ] || continue
        cd "$FLEET_DIR/$_smp" || continue
        if guard_should_skip; then
            echo -e "${RED}🛑 SKIP $_smp: ${GUARD_REASON} — leaving on its branch, not pulling main.${NC}"
            case " $SKIPPED_SUBMODULES " in *" $_smp "*) : ;; *) SKIPPED_SUBMODULES="$SKIPPED_SUBMODULES $_smp" ;; esac
        else
            git checkout main 2>&1 | tail -1 && git pull origin main 2>&1 | tail -2
        fi
        cd "$FLEET_DIR"
    done < <(git submodule status)
fi
echo

# ============================================================================
# VERIFICATION: Ensure all submodules are synced with remote before commit
# ============================================================================
echo -e "${CYAN}Verifying all submodules match remote before committing main...${NC}"
if [ "$DRY_RUN" = false ]; then
    OUT_OF_SYNC_SUBMODULES=""

    # Check each submodule
    while IFS= read -r submodule_line; do
        # Extract submodule path (second field)
        sm_path=$(echo "$submodule_line" | awk '{print $2}')
        # SAFETY GUARD: skip verification for guarded/skipped submodules (they
        # intentionally sit on their own branch, ahead of origin/main).
        case " $SKIPPED_SUBMODULES " in
            *" $sm_path "*)
                echo -e "${YELLOW}  (skipping sync-check for guarded $sm_path)${NC}"
                continue
                ;;
        esac
        if [ -n "$sm_path" ] && [ -d "$FLEET_DIR/$sm_path" ]; then
            cd "$FLEET_DIR/$sm_path"

            # Fetch to get latest remote state
            git fetch origin main 2>/dev/null || true

            LOCAL_HEAD=$(git rev-parse HEAD 2>/dev/null)
            REMOTE_HEAD=$(git rev-parse origin/main 2>/dev/null)

            if [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
                OUT_OF_SYNC_SUBMODULES="$OUT_OF_SYNC_SUBMODULES\n  - $sm_path (local: ${LOCAL_HEAD:0:7}, remote: ${REMOTE_HEAD:0:7})"
            fi

            cd "$FLEET_DIR"
        fi
    done < <(git submodule status)

    if [ -n "$OUT_OF_SYNC_SUBMODULES" ]; then
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${RED}⚠️  SUBMODULES OUT OF SYNC WITH REMOTE${NC}"
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}The following submodules do not match remote:${NC}"
        echo -e "$OUT_OF_SYNC_SUBMODULES"
        echo
        echo -e "${YELLOW}OPTIONS:${NC}"
        echo "  1. Pull again: git submodule foreach 'git pull origin main'"
        echo "  2. Check if submodule pushes failed and re-push manually"
        echo "  3. Continue anyway (risk: stale submodule pointers in main)"
        echo
        echo -e "${CYAN}Stopping before main commit. Resolve submodule sync, then re-run.${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ All submodules verified in sync with remote${NC}"
    fi
fi
echo

# Check for conflicts
if [ "$DRY_RUN" = false ]; then
    if git status --porcelain | grep -q '^UU'; then
        echo -e "${RED}⚠️  CONFLICTS DETECTED in parent module!${NC}"
        git status --porcelain | grep '^UU'
        echo
        echo -e "${YELLOW}CONFLICT RESOLUTION STEPS:${NC}"
        echo "  1. Resolve content conflicts (script files, etc.)"
        echo "  2. git add .  # Stage all changes"
        echo "  3. git commit -m '${COMMIT_NUMBER}'  # Use SAME commit number"
        echo "  4. git push origin main"
        echo
        echo -e "${CYAN}NOTE: Submodule pointer conflicts should already be resolved by submodule update${NC}"
        echo -e "${CYAN}NOTE: All submodules already processed - do NOT re-run script${NC}"
        echo -e "${GREEN}✓ Consolidation complete after manual push${NC}"
        exit 1
    fi
fi

# Commit
show_cmd "git add ."
exec_cmd git add .

# SAFETY GUARD: hold back guarded submodule pointers (unpushed branch work).
if [ "$DRY_RUN" = false ]; then
    for _s in $SKIPPED_SUBMODULES; do
        git restore --staged "$_s" 2>/dev/null || true
        echo -e "${YELLOW}  (held back guarded submodule pointer: $_s)${NC}"
    done
fi

show_cmd "git commit -m '${COMMIT_NUMBER}'"
if [ "$DRY_RUN" = false ]; then
    # Check if there's anything to commit
    if [ -n "$(git status --porcelain)" ]; then
        git commit -m "${COMMIT_NUMBER}"
    else
        echo -e "${CYAN}  No changes to commit${NC}"
    fi
fi

# Push
show_cmd "git push origin main"
exec_cmd git push origin main

echo
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ CONSOLIDATION COMPLETE FOR $SYSTEM_NAME${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# SAFETY GUARD summary
if [ -n "${SKIPPED_SUBMODULES// /}" ]; then
    echo -e "${RED}🛑 GUARDED (left untouched — unmerged branch/detached work):${NC}"
    for _s in $SKIPPED_SUBMODULES; do echo -e "${RED}   - $_s${NC}"; done
    echo -e "${YELLOW}   These were NOT synced. Merge their branch into main manually when ready.${NC}"
    echo
fi

if [ "$DRY_RUN" = false ]; then
    echo -e "${CYAN}Current commit:${NC} $(git rev-parse --short HEAD)"
    echo

    echo -e "${YELLOW}Next steps:${NC}"
    if [[ "$SYSTEM_NAME" == *"Instance 2"* ]]; then
        echo "  1. ✅ Instance 2 complete"
        echo "  2. Next: Run this script on Instance 1"
        echo "     ssh -i ${SYSMON_SSH_KEY:-<ssh-key>} ubuntu@${IP1:-<instance-1-ip>}"
        echo "     cd ~/fleet && ./docs/scripts/multi-system/bulk-stash-pull-pop-push.sh"
    elif [[ "$SYSTEM_NAME" == *"Instance 1"* ]]; then
        echo "  1. ✅ Instance 2 complete"
        echo "  2. ✅ Instance 1 complete"
        echo "  3. Next: Run this script on Local"
        echo "     cd ~/fleet && ./docs/scripts/multi-system/bulk-stash-pull-pop-push.sh"
    elif [[ "$SYSTEM_NAME" == "Local" ]]; then
        echo "  1. ✅ Instance 2 complete"
        echo "  2. ✅ Instance 1 complete"
        echo "  3. ✅ Local complete"
        echo
        echo -e "${GREEN}All systems consolidated!${NC}"
    fi
fi
echo
