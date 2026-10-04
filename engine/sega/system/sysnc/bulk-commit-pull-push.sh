#!/bin/bash

# ⚠️ SUPERSEDED by fleet-sync.sh (same dir) — the cohesive tool: `fleet-sync.sh sync` runs this
#    (push phase) AND the convergence-pull across all reachable hosts in one command. This script
#    is the per-host push engine only and does NOT pull laggards. Prefer fleet-sync.sh.
#
# FLEET Bulk Commit-Pull-Push (WIP Integration) — the NON-STASH counterpart to bulk-stash-pull-pop-push.sh
#
# Safely integrates work-in-progress across systems by COMMITTING (never stashing) each repo's WIP,
# then merging origin/main. Git auto-merges non-overlapping work; genuine same-line overlaps surface
# as CONFLICTS which are reported and HELD (never auto-resolved) for deliberate manual resolution.
#
#   Per repo (every submodule + parent) — PUSH-FIRST (operator rule: try push before any fetch/merge):
#     1. git add -A && commit   (WIP becomes a real commit — reversible, never stranded in a stash)
#     2. git push origin HEAD:main   (FIRST — if remote hasn't moved this lands with no merge commit)
#     3. push rejected (non-ff) -> git fetch origin; git merge origin/main
#          clean  -> git push again
#          CONFLICT -> capture conflicted files, `git merge --abort`, WIP stays committed, DO NOT push, REPORT
#
# Push-first (not pull-first): pulling first manufactures avoidable merge commits when the remote has not
# moved. Only fall through to fetch+merge when the push is actually rejected. See common/docs/process/SYNC_JOURNAL.md.
# .env IS COMMITTED like any other file — no exclusion (operator directive; secrets are already tracked fleet-wide).
#
# WHY (not stash): a stash that isn't popped strands work and hides it from integration. Committing makes
# WIP a first-class object that merges, surfaces real conflicts, and survives aborts. See the fleet-ops
# runbook and [[feedback_audit_uncommitted_before_synced]] / [[feedback_merge_conflict_resolution]].
#
# Run this on EACH system in turn. Each run pulls in every prior system's pushes, so overlaps between
# systems surface as conflicts exactly where two systems touched the same lines.
#
# Usage:  ./bulk-commit-pull-push.sh [host_label] [commit_message]
#         host_label defaults to $(hostname -s); message defaults to "WIP integrate (<host>, <date>)".
#
# NO EXCLUSIONS: every submodule (incl. atlas, sega) + parent are processed; git's .gitignore
# alone decides what is tracked. If you need to exclude a repo, do it deliberately via SKIP_REPOS.
#
# ABSOLUTE INVARIANTS (do not weaken):
#   - never auto-resolve a conflict (abort + report only)
#   - never discard work (commit, never `checkout`/`reset --hard`/`clean`; conflicts abort to the commit)

set -o pipefail

EXPECTED_DIR="$HOME/fleet"
cd "$EXPECTED_DIR" 2>/dev/null || { echo "ERROR: $EXPECTED_DIR not found"; exit 1; }

HOST_LABEL="${1:-$(hostname -s)}"
DATE_TAG="$(date +%Y-%m-%d)"
COMMIT_MSG="${2:-WIP integrate ($HOST_LABEL, $DATE_TAG)}"
LOG_FILE="/tmp/bulk_commit_pull_push_$(date +%Y%m%d_%H%M%S).log"

# IPv4-forced SSH: some hosts (e.g. node-1) have a flaky IPv6 route to gitlab that silently times out.
GS='ssh -4 -o ConnectTimeout=25'

# Optional deliberate skips (space-separated submodule paths). Empty by default = process everything.
SKIP_REPOS="${SKIP_REPOS:-}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log() { echo -e "$1$2${NC}" | tee -a "$LOG_FILE"; }

CONFLICTS=(); PUSHED=(); COMMITTED=(); PUSHFAIL=(); NOOP=(); BRANCHHELD=(); BRANCHHELD_PATHS=(); PUSH_UNVERIFIED=()

is_skipped() {
  local x="$1"; for r in $SKIP_REPOS; do [ "$r" = "$x" ] && return 0; done; return 1
}

# Confirm a push actually LANDED: the push above pushed HEAD:main, so the remote refs/heads/main sha
# must now equal local HEAD. node-1's flaky IPv6 route to gitlab can make a push report success without
# landing (root CLAUDE.md: "a 'successful' push that doesn't land is the tell"). A failed or EMPTY
# ls-remote is treated as UNVERIFIED (warn), never as a silent PASS, so the failure mode fails loud.
# Equality (not ancestry) is deliberate: the failure mode leaves the remote UNCHANGED, which equality
# catches exactly. If a concurrent host advances origin/main past our HEAD right after we push, this
# warns benignly (our commit still landed as an ancestor); that is acceptable and needs no fetch.
verify_landed() {
  local label="$1" d="$2" remote_sha local_sha
  remote_sha=$(GIT_SSH_COMMAND="$GS" git -C "$d" ls-remote origin refs/heads/main 2>>"$LOG_FILE" | awk 'NR==1{print $1}')
  local_sha=$(git -C "$d" rev-parse HEAD 2>>"$LOG_FILE")
  if [ -z "$remote_sha" ] || [ "$remote_sha" != "$local_sha" ]; then
    PUSH_UNVERIFIED+=("$label (remote=${remote_sha:-<none>} local=$local_sha)")
    log "$YELLOW" "  ⚠ PUSH-UNVERIFIED $label — push reported success but remote sha != local HEAD (re-check: git ls-remote origin main)"
    return 1
  fi
  return 0
}

integrate() {
  local label="$1" d="$2"

  # git lock guard
  if [ -f "$d/.git/index.lock" ]; then log "$RED" "  ⚠ LOCK     $label — .git/index.lock present, skipping"; return; fi

  local br; br=$(git -C "$d" rev-parse --abbrev-ref HEAD 2>/dev/null)

  # 1. commit WIP — NO exclusions; .env is committed like any other file (operator directive; see SYNC_JOURNAL.md)
  git -C "$d" add -A 2>>"$LOG_FILE"
  # PARENT: never capture a branch-held submodule's feature-branch gitlink — unstage it so the parent keeps
  # its recorded (origin/main) pointer. Prevents a dangling parent→submodule reference (see SYNC_JOURNAL 2026-07-20).
  if [ "$label" = "PARENT" ] && [ "${#BRANCHHELD_PATHS[@]}" -gt 0 ]; then
    for bp in "${BRANCHHELD_PATHS[@]}"; do git -C "$d" reset -q -- "$bp" 2>>"$LOG_FILE"; done
  fi
  local staged; staged=$(git -C "$d" diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
  if [ "$staged" -gt 0 ]; then
    git -C "$d" commit -q -m "$COMMIT_MSG" 2>>"$LOG_FILE"
  fi

  # BRANCH GUARD (submodules only): never auto-promote a named non-main branch to main. WIP is committed
  # locally (never lost) but NOT pushed; the parent keeps its main pointer (unstaged above). Detached
  # ("HEAD") @ origin/main is the normal fleet state and still pushes HEAD:main.
  if [ "$label" != "PARENT" ] && [ "$br" != "main" ] && [ "$br" != "HEAD" ]; then
    BRANCHHELD+=("$label (br=$br, WIP=$staged)"); BRANCHHELD_PATHS+=("$label")
    log "$YELLOW" "  ⎇ BRANCH-HELD $label (br=$br, WIP=$staged committed locally; NOT pushed to main)"
    return
  fi

  # only push against origin/main if it exists on the remote
  if ! GIT_SSH_COMMAND="$GS" git -C "$d" ls-remote --exit-code origin main >/dev/null 2>&1; then
    [ "$staged" -gt 0 ] && { COMMITTED+=("$label"); log "$GREEN" "  ✓ committed $label ($staged files; no origin/main to push)"; }
    return
  fi

  # 2. PUSH — GATED behind SYNC_ALLOW_PUSH (default OFF), added after the 2026-08 silent-revert
  #    incidents: a push-FIRST fast-forward can land a stale/reverted working tree with NO conflict,
  #    silently reverting a committed fix (dropped _stage_host_assets / cloud-init export-dirs /
  #    the CPU-torch Dockerfile line). WIP is ALWAYS committed above (preserved, never stranded);
  #    pushing is now a DELIBERATE, reviewed act. See feedback_sync_never_revert_committed_work.
  if [ "${SYNC_ALLOW_PUSH:-0}" != "1" ]; then
    GIT_SSH_COMMAND="$GS" git -C "$d" fetch -q origin 2>>"$LOG_FILE"
    local ahX bhX; ahX=$(git -C "$d" rev-list --count origin/main..HEAD 2>/dev/null); bhX=$(git -C "$d" rev-list --count HEAD..origin/main 2>/dev/null)
    if [ "$staged" -gt 0 ] || [ "${ahX:-0}" -gt 0 ]; then
      COMMITTED+=("$label"); log "$YELLOW" "  ✓ committed $label (WIP=$staged, ahead=${ahX:-0} behind=${bhX:-0}) — NOT pushed; review then re-run with SYNC_ALLOW_PUSH=1"
    else
      NOOP+=("$label")
    fi
    return
  fi

  # 2b. PUSH FIRST — try to push before any fetch/merge. If the remote hasn't moved this lands cleanly
  #    with no merge commit. "Everything up-to-date" also succeeds here → NOOP.
  if GIT_SSH_COMMAND="$GS" git -C "$d" push origin HEAD:main >>"$LOG_FILE" 2>&1; then
    local ah; ah=$(git -C "$d" rev-list --count origin/main..HEAD 2>/dev/null)
    if [ "${ah:-0}" -gt 0 ] || [ "$staged" -gt 0 ]; then
      PUSHED+=("$label"); log "$GREEN" "  ✓ PUSHED   $label (WIP=$staged, push-first)"; verify_landed "$label" "$d"
    else
      NOOP+=("$label")
    fi
    return
  fi

  # 3. push rejected → NOW fetch + merge (only on reject). Conflict = abort + hold + report, never auto-resolve.
  GIT_SSH_COMMAND="$GS" git -C "$d" fetch -q origin 2>>"$LOG_FILE"
  if ! git -C "$d" merge --no-edit origin/main >>"$LOG_FILE" 2>&1; then
    local cf; cf=$(git -C "$d" diff --name-only --diff-filter=U 2>/dev/null | tr '\n' ',' | sed 's/,$//')
    git -C "$d" merge --abort 2>>"$LOG_FILE"
    CONFLICTS+=("$label :: $cf")
    log "$RED" "  ✗ CONFLICT $label ($staged WIP committed+held): $cf"
    return
  fi

  # 4. merged clean → push again
  if GIT_SSH_COMMAND="$GS" git -C "$d" push origin HEAD:main >>"$LOG_FILE" 2>&1; then
    PUSHED+=("$label"); log "$GREEN" "  ✓ PUSHED   $label (WIP=$staged, merged-on-reject+pushed)"; verify_landed "$label" "$d"
  else
    PUSHFAIL+=("$label"); log "$YELLOW" "  ⚠ PUSHFAIL $label (committed+merged, push still rejected — inspect $LOG_FILE)"
  fi
}

log "$BLUE" "═══ bulk-commit-pull-push  host=$HOST_LABEL  $(date)  log=$LOG_FILE ═══"
[ -n "$SKIP_REPOS" ] && log "$YELLOW" "  (deliberate skips: $SKIP_REPOS)"

SUBS=$(git config -f .gitmodules --get-regexp path 2>/dev/null | awk '{print $2}')
log "$BLUE" "── submodules ──"
for s in $SUBS; do
  [ -e "$s/.git" ] || continue
  is_skipped "$s" && { log "$YELLOW" "  ⤳ SKIP     $s"; continue; }
  integrate "$s" "$PWD/$s"
done
log "$BLUE" "── parent ──"
integrate "PARENT" "$PWD"

log "$BLUE" "═══ SUMMARY ($HOST_LABEL) ═══"
log "$GREEN"  "  pushed:    ${#PUSHED[@]}   committed-only: ${#COMMITTED[@]}   noop: ${#NOOP[@]}"
[ "${#BRANCHHELD[@]}" -gt 0 ] && { log "$YELLOW" "  BRANCH-HELD: ${#BRANCHHELD[@]} (committed locally, not pushed to main)"; for b in "${BRANCHHELD[@]}"; do log "$YELLOW" "     - $b"; done; }
log "$RED"    "  CONFLICTS: ${#CONFLICTS[@]}"
for c in "${CONFLICTS[@]}"; do log "$RED" "     - $c"; done
[ "${#PUSHFAIL[@]}" -gt 0 ] && { log "$YELLOW" "  PUSHFAIL: ${#PUSHFAIL[@]}"; for p in "${PUSHFAIL[@]}"; do log "$YELLOW" "     - $p"; done; }
[ "${#PUSH_UNVERIFIED[@]}" -gt 0 ] && { log "$YELLOW" "  PUSH-UNVERIFIED: ${#PUSH_UNVERIFIED[@]} (push reported success but remote sha != local HEAD; re-run or check git ls-remote origin main)"; for u in "${PUSH_UNVERIFIED[@]}"; do log "$YELLOW" "     - $u"; done; }
log "$BLUE" "  parent HEAD now: $(git rev-parse --short HEAD)"
# non-zero exit if conflicts remain to integrate, so callers/CI can gate
[ "${#CONFLICTS[@]}" -eq 0 ]
