#!/bin/bash

# ⚠️ SUPERSEDED by fleet-sync.sh (same dir): `fleet-sync.sh converge` commits WIP first (this script
#    BLOCKS on dirty), pushes anything ahead, and auto-resolves submodule-gitlink conflicts. Prefer it.
#
# FLEET Bulk Pull (NON-STASH) — the pull counterpart to bulk-commit-pull-push.sh, and the non-stash
# alternative to gitlab-bulk-pull.sh (which auto-stashes and thereby HIDES overlaps).
#
# Pulls origin/main into every submodule + parent WITHOUT stashing, so any local work-in-progress
# that overlaps incoming changes SURFACES as a conflict (or a merge-blocked) instead of being masked.
# This is the VERIFY-from-the-pull-direction pass: confirm each system can cleanly receive the fleet's
# integrated work, and see exactly where it can't.
#
#   Per repo:
#     fetch origin
#     if behind origin/main:
#       git merge --no-edit origin/main
#         clean            -> UPDATED (report new head)
#         merge conflict   -> capture files, `git merge --abort`, report CONFLICT (WIP untouched)
#         blocked-by-dirty -> report BLOCKED (local uncommitted changes overlap incoming; commit them
#                              first with bulk-commit-pull-push.sh, then re-pull)
#     else -> up-to-date
#
# Read-only-ish: never stashes, never commits, never pushes, never discards. A conflicting/blocked repo
# is left exactly as found (local WIP intact) for deliberate handling. Resolve per the ABSOLUTE rules:
# union-reconcile, never force-select a side, never lose work. See FLEET_OPERATIONS.md.
#
# Usage:  ./bulk-pull.sh [host_label]

set -o pipefail
cd "$HOME/fleet" 2>/dev/null || { echo "ERROR: ~/fleet not found"; exit 1; }
HOST_LABEL="${1:-$(hostname -s)}"
LOG_FILE="/tmp/bulk_pull_$(date +%Y%m%d_%H%M%S).log"
GS='ssh -4 -o ConnectTimeout=25'   # node-1's IPv6→gitlab route flakes; force IPv4
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log() { echo -e "$1$2${NC}" | tee -a "$LOG_FILE"; }

CONFLICTS=(); BLOCKED=(); UPDATED=(); UPTODATE=()

pull_repo() {
  local label="$1" d="$2"
  GIT_SSH_COMMAND="$GS" git -C "$d" fetch -q origin 2>>"$LOG_FILE"
  git -C "$d" rev-parse --verify -q origin/main >/dev/null 2>&1 || return
  local beh; beh=$(git -C "$d" rev-list --count HEAD..origin/main 2>/dev/null)
  if [ "${beh:-0}" -eq 0 ]; then UPTODATE+=("$label"); return; fi
  # attempt no-stash merge
  local out; out=$(git -C "$d" merge --no-edit origin/main 2>&1)
  if [ -n "$(git -C "$d" diff --name-only --diff-filter=U 2>/dev/null)" ]; then
    local cf; cf=$(git -C "$d" diff --name-only --diff-filter=U | tr '\n' ',' | sed 's/,$//')
    git -C "$d" merge --abort 2>>"$LOG_FILE"
    CONFLICTS+=("$label :: $cf"); log "$RED" "  ✗ CONFLICT $label (WIP intact): $cf"
  elif echo "$out" | grep -qiE 'would be overwritten|Please commit|Please, commit'; then
    BLOCKED+=("$label"); log "$YELLOW" "  ⚠ BLOCKED  $label — local uncommitted WIP overlaps incoming (commit first, then re-pull)"
  else
    UPDATED+=("$label"); log "$GREEN" "  ✓ UPDATED  $label → $(git -C "$d" rev-parse --short HEAD)"
  fi
}

log "$BLUE" "═══ bulk-pull (non-stash)  host=$HOST_LABEL  $(date)  log=$LOG_FILE ═══"
log "$BLUE" "── submodules ──"
for s in $(git config -f .gitmodules --get-regexp path 2>/dev/null | awk '{print $2}'); do
  [ -e "$s/.git" ] && pull_repo "$s" "$PWD/$s"
done
log "$BLUE" "── parent ──"
pull_repo "PARENT" "$PWD"
# after a clean parent pull, refresh submodule checkouts to the new gitlinks (no-op if unchanged)
git submodule update --init --recursive >/dev/null 2>&1

log "$BLUE" "═══ SUMMARY ($HOST_LABEL) ═══"
log "$GREEN" "  updated: ${#UPDATED[@]}   up-to-date: ${#UPTODATE[@]}"
log "$RED"   "  CONFLICTS: ${#CONFLICTS[@]}"; for c in "${CONFLICTS[@]}"; do log "$RED" "     - $c"; done
[ "${#BLOCKED[@]}" -gt 0 ] && { log "$YELLOW" "  BLOCKED (uncommitted WIP): ${#BLOCKED[@]}"; for b in "${BLOCKED[@]}"; do log "$YELLOW" "     - $b"; done; }
log "$BLUE" "  parent HEAD now: $(git rev-parse --short HEAD)"
[ "${#CONFLICTS[@]}" -eq 0 ]
