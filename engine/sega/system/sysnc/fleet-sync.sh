#!/bin/bash
# fleet-sync.sh — the cohesive fleet git-sync tool (the hourly cross-host op).
#
# ┌──────────────────────────────────────────────────────────────────────────────────────────┐
# │ ⚠ NOT APPROVED FOR AUTONOMOUS MULTI-HOST ORCHESTRATION (operator directive, 2026-08-07).   │
# │ The principal never approved the all-hosts orchestrator. In practice the cross-host cycle   │
# │ CHASES A MOVING TARGET: a repo under live development (e.g. atlas) keeps advancing on   │
# │ one host, so every converge mints a fresh gitlink merge commit and the other hosts never    │
# │ reach a simultaneous 0/0 — it just churns origin. It also masks per-host realities (a       │
# │ full disk, a down mini) behind a single summary line.                                       │
# │                                                                                             │
# │ USE ONE SYSTEM AT A TIME. Handle each host individually with visibility. The multi-host     │
# │ path (default host list, or --hosts with >1 entry) now HARD-REFUSES unless you pass         │
# │ --i-approve-multihost explicitly. Prefer: fleet-sync.sh <cmd> --host <H>  (or --local).     │
# │ For anything non-trivial (conflicts, disk, off-main branches), prefer direct per-repo git   │
# │ over this tool. See feedback: handle each instance individually.                            │
# └──────────────────────────────────────────────────────────────────────────────────────────┘
#
# Consolidates what used to be bulk-commit-pull-push.sh (push) + bulk-pull.sh (pull) into ONE tool
# with the full workflow and host orchestration. Replaces the ad-hoc /tmp scripts.
#
# USAGE:  fleet-sync.sh <push|converge|sync|state> [scope]
#
# SUBCOMMANDS
#   push       Per repo (submodule+parent): commit WIP -> push-first (HEAD:main); on non-ff reject ->
#              fetch+merge origin/main -> push. Conflict = abort + HOLD + report (never auto-resolve).
#   converge   Per repo: commit WIP -> merge origin/main (PULL down) -> push if ahead -> auto-resolve
#              ONLY submodule-gitlink conflicts to the sub's origin/main tip. Closes the push-first gap
#              (a behind-only repo is never pulled by push alone — that was the "forgotten" step).
#   sync       push across all hosts, THEN converge across all hosts (the full cycle — see Rule 10).
#   state      Per host: parent + submodule ahead/behind vs origin/main; flags anything not on main.
#
# SCOPE (default = orchestrate across all reachable $FLEET_HOSTS)
#   --local          run the per-host engine on THIS host only (no ssh)
#   --hosts "a b c"  override host list        --host H   single host        (env: FLEET_HOSTS)
#
# SAFEGUARDS against sweeping live work (2026-08-01, after an uncommitted engine patch was lost):
#   1. SKIP live-edited repos: `FLEET_SKIP="atlas swarm"` or a `.fleet-sync-skip` file in the repo
#      root → that repo is left entirely untouched. Use while an agent is actively editing a submodule.
#   2. WIP snapshot: any repo with uncommitted work gets its WIP committed AND pinned to a durable ref
#      `refs/fleet-sync/presync-<ts>` — so even if a later reset/merge moves HEAD, the work is recoverable
#      (`git show refs/fleet-sync/presync-<ts>`), not stranded in the expiring reflog.
#   3. (REMOVED 2026-08-08) The old ~/.fleet-sync-backups tarball step filled disks (100+ GB/host);
#      WIP is already preserved by the commit (safeguard 2 / Rule 3). Do not reintroduce it.
#
# ABSOLUTE RULES (do not weaken — see common/docs/process/SYNC_JOURNAL.md):
#   1. Never lose work: commit (never stash); .env IS committed (no exclusion).
#   2. Never auto-resolve a CONTENT conflict — abort+hold+report for per-file human judgment.
#      Auto-resolve ONLY a submodule-gitlink conflict (advance to the sub's origin/main tip).
#   3. Branch guard: never push a named non-main branch to main; the parent keeps its origin/main
#      gitlink for a branch-held sub (never captures the feature-branch tip -> no dangling pointer).
#   4. Force `ssh -4` (node-1 IPv6->gitlab flake); a "successful" push that didn't land is the tell.
#   5. Orchestration skips UNREACHABLE hosts (reports them) — a down node never blocks the fleet.
set -o pipefail
CMD="${1:-sync}"; shift 2>/dev/null
LOCAL=0; MULTI_OK=0; HOST_SET=0; HOSTS="${FLEET_HOSTS:-dev-laptop node-1 node-2 node-3 node-4}"
while [ $# -gt 0 ]; do
  case "$1" in
    --local) LOCAL=1; HOST_SET=1 ;;
    --hosts) shift; HOSTS="$1"; HOST_SET=1 ;;
    --host)  shift; HOSTS="$1"; HOST_SET=1 ;;
    --i-approve-multihost) MULTI_OK=1 ;;   # explicit operator opt-in; see the warning header
  esac; shift
done
# GUARD (2026-08-07 operator directive): one system at a time. Refuse the multi-host path unless
# the operator explicitly opts in. This covers (a) no scope flag given → the default all-hosts list,
# and (b) --hosts with more than one entry. Single --host / --local always allowed.
if [ "$LOCAL" != 1 ] && [ "$MULTI_OK" != 1 ]; then
  _nh=$(printf '%s\n' $HOSTS | grep -c .)
  if [ "$HOST_SET" != 1 ] || [ "${_nh:-0}" -gt 1 ]; then
    echo "REFUSED: multi-host orchestration is not approved (operator directive 2026-08-07)." >&2
    echo "  Run one system at a time:  $(basename "$0") $CMD --host <HOST>   (or --local)" >&2
    echo "  Hosts you could target individually: $HOSTS" >&2
    echo "  To override deliberately (not recommended): add --i-approve-multihost" >&2
    exit 2
  fi
fi
# -4: node-1 IPv6->gitlab flake. ServerAlive*: abort a STALLED transfer (~30s) so a stuck push/fetch
# can't hang the whole run (ConnectTimeout only guards the connect, not a mid-transfer stall — this was
# the overnight-hang bug). BatchMode: never block on a credential/host-key prompt.
GS='ssh -4 -o ConnectTimeout=20 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -o BatchMode=yes'
export GIT_SSH_COMMAND="$GS"
DATE_TAG="$(date +%F 2>/dev/null || echo undated)"
RUNTS="$(date +%Y%m%dT%H%M%S 2>/dev/null || echo run)"
# SAFEGUARD 1 — leave actively-worked repos ALONE. A repo is skipped if it's in FLEET_SKIP
# (e.g. FLEET_SKIP="atlas swarm") OR has a `.fleet-sync-skip` marker file at its root. Use this
# when an agent is live-editing a submodule so the auto-sync never touches (and never sweeps) their WIP.
SKIP="${FLEET_SKIP:-}"
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'; BLU='\033[0;34m'; NC='\033[0m'

# ───────────────────────────── per-host engine ─────────────────────────────
_msg() { echo "WIP integrate (fleet-sync $1, $(hostname -s), $DATE_TAG)"; }

# resolve every conflicted submodule-gitlink in $d to the sub's origin/main tip; echo any NON-gitlink
# (content) conflict paths (which must be held). returns 0 if only gitlinks remained.
_resolve_gitlinks() {
  local d="$1" nong=""
  for p in $(git -C "$d" diff --name-only --diff-filter=U 2>/dev/null); do
    if git -C "$d" ls-files -s "$p" 2>/dev/null | grep -q '^160000'; then
      local tip; tip=$(git -C "$d" -C "$p" rev-parse origin/main 2>/dev/null)
      [ -n "$tip" ] && git -C "$d" update-index --cacheinfo 160000,"$tip","$p" 2>/dev/null
    else nong="$nong $p"; fi
  done
  [ -z "$nong" ] && return 0
  echo "$nong"; return 1
}

engine() {  # $1 = push|converge
  local mode="$1" msg; msg="$(_msg "$mode")"
  cd "$HOME/fleet" 2>/dev/null || { echo "ERR: ~/fleet not found on $(hostname -s)"; return 2; }
  local P=0 M=0 U=0 N=0 BH=0 CF=0 SK=0 PU=0; local -a HELD=(); local -a BRANCH=(); local -a BRANCH_PATHS=(); local -a SKIPPED=(); local -a UNVER=()
  local repos; repos=$(git config -f .gitmodules --get-regexp path 2>/dev/null | awk '{print $2}')
  # Confirm a push actually LANDED: the push pushed HEAD:main, so remote refs/heads/main must now equal
  # local HEAD. node-1's flaky IPv6 route can make a push report success without landing (Rule 4 above).
  # A failed or EMPTY ls-remote is recorded UNVERIFIED (warn), never a silent PASS — fail loud.
  # Equality (not ancestry) is deliberate: the failure mode leaves origin/main UNCHANGED, caught exactly.
  # A concurrent host advancing origin/main past our HEAD warns benignly (our commit landed as ancestor).
  _landed() {
    local label="$1" d="$2" rs ls
    rs=$(GIT_SSH_COMMAND="$GS" git -C "$d" ls-remote origin refs/heads/main 2>/dev/null | awk 'NR==1{print $1}')
    ls=$(git -C "$d" rev-parse HEAD 2>/dev/null)
    if [ -z "$rs" ] || [ "$rs" != "$ls" ]; then UNVER+=("$label (remote=${rs:-<none>} local=$ls)"); PU=$((PU+1)); fi
  }
  _one() {
    local label="$1" d="$2"
    [ -f "$d/.git/index.lock" ] && return
    # SAFEGUARD 1: skip actively-worked repos entirely — never touch (never sweep) live edits
    if [ -f "$d/.fleet-sync-skip" ] || printf ' %s ' $SKIP 2>/dev/null | grep -q " $label "; then
      SKIPPED+=("$label"); SK=$((SK+1)); return
    fi
    local br; br=$(git -C "$d" rev-parse --abbrev-ref HEAD 2>/dev/null)
    # SAFEGUARD 3 REMOVED (operator directive 2026-08-08): the ~/.fleet-sync-backups tarball of every
    # dirty file before each op grew to 100+ GB per host and filled disks (node-1/node-2 hit 100%).
    # WIP is already preserved by the commit below (Rule 3: commit never stash) — the tarball was
    # redundant. Do NOT reintroduce a filesystem-backup step here.
    git -C "$d" add -A 2>/dev/null
    # parent must not capture a branch-held sub's feature gitlink
    if [ "$label" = PARENT ] && [ "${#BRANCH_PATHS[@]}" -gt 0 ]; then
      for bp in "${BRANCH_PATHS[@]}"; do git -C "$d" reset -q -- "$bp" 2>/dev/null; done
    fi
    local st; st=$(git -C "$d" diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
    # SAFEGUARD 2: commit WIP, then PIN it to a durable ref so a later reset/merge can't lose it.
    # (the git-add-A commit alone wasn't enough — a subsequent reset left it only in the expiring reflog.)
    [ "$st" -gt 0 ] && { git -C "$d" commit -q -m "$msg" 2>/dev/null; git -C "$d" update-ref "refs/fleet-sync/presync-$RUNTS" HEAD 2>/dev/null; }
    # branch guard (submodules): never auto-promote a named non-main branch to main
    if [ "$label" != PARENT ] && [ "$br" != main ] && [ "$br" != HEAD ]; then
      BRANCH+=("$label($br,wip=$st)"); BRANCH_PATHS+=("$label"); BH=$((BH+1)); return
    fi
    git -C "$d" rev-parse --verify -q origin/main >/dev/null 2>&1 || \
      GIT_SSH_COMMAND="$GS" git -C "$d" fetch -q origin main 2>/dev/null
    local behind ahead
    # PUSH GATE (2026-08 silent-revert fix): default = commit + report, NO push. A push-first
    # fast-forward can land a stale/reverted working tree with no conflict, silently reverting a
    # committed fix. WIP is committed + pinned above (preserved), so pushing is now DELIBERATE.
    # Set SYNC_ALLOW_PUSH=1 to push after review. See feedback_sync_never_revert_committed_work.
    if [ "${SYNC_ALLOW_PUSH:-0}" != "1" ]; then
      GIT_SSH_COMMAND="$GS" git -C "$d" fetch -q origin main 2>/dev/null
      ahead=$(git -C "$d" rev-list --count origin/main..HEAD 2>/dev/null); behind=$(git -C "$d" rev-list --count HEAD..origin/main 2>/dev/null)
      if [ "${ahead:-0}" -gt 0 ] || [ "$st" -gt 0 ]; then HELD+=("$label ::committed-not-pushed ahead=${ahead:-0} behind=${behind:-0} (SYNC_ALLOW_PUSH=1 to push)"); else N=$((N+1)); fi
      return
    fi
    if [ "$mode" = converge ]; then
      GIT_SSH_COMMAND="$GS" git -C "$d" fetch -q origin main 2>/dev/null
      behind=$(git -C "$d" rev-list --count HEAD..origin/main 2>/dev/null)
      if [ "${behind:-0}" -gt 0 ]; then
        if ! git -C "$d" merge --no-edit origin/main >/dev/null 2>&1; then
          local bad; bad=$(_resolve_gitlinks "$d") || { git -C "$d" merge --abort 2>/dev/null; HELD+=("$label ::$bad"); CF=$((CF+1)); return; }
          git -C "$d" commit --no-edit -q 2>/dev/null
        fi
        U=$((U+1))
      fi
      ahead=$(git -C "$d" rev-list --count origin/main..HEAD 2>/dev/null)
      if [ "${ahead:-0}" -gt 0 ]; then if GIT_SSH_COMMAND="$GS" git -C "$d" push origin HEAD:main >/dev/null 2>&1; then P=$((P+1)); _landed "$label" "$d"; else HELD+=("$label ::push-failed"); fi; fi
      [ "${behind:-0}" -eq 0 ] && [ "${ahead:-0}" -eq 0 ] && N=$((N+1))
      return
    fi
    # mode = push (push-first, merge-on-reject)
    if GIT_SSH_COMMAND="$GS" git -C "$d" push origin HEAD:main >/dev/null 2>&1; then
      ahead=$(git -C "$d" rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
      if { [ "${ahead:-0}" -gt 0 ] || [ "$st" -gt 0 ]; }; then P=$((P+1)); _landed "$label" "$d"; else N=$((N+1)); fi; return
    fi
    GIT_SSH_COMMAND="$GS" git -C "$d" fetch -q origin 2>/dev/null
    if git -C "$d" merge --no-edit origin/main >/dev/null 2>&1; then
      if GIT_SSH_COMMAND="$GS" git -C "$d" push origin HEAD:main >/dev/null 2>&1; then M=$((M+1)); _landed "$label" "$d"; else HELD+=("$label ::push-failed"); fi
    else
      local bad; bad=$(_resolve_gitlinks "$d")
      if [ $? -eq 0 ]; then git -C "$d" commit --no-edit -q 2>/dev/null; if GIT_SSH_COMMAND="$GS" git -C "$d" push origin HEAD:main >/dev/null 2>&1; then M=$((M+1)); _landed "$label" "$d"; else HELD+=("$label ::push-failed"); fi
      else git -C "$d" merge --abort 2>/dev/null; HELD+=("$label ::$bad"); CF=$((CF+1)); fi
    fi
  }
  for s in $repos; do [ -e "$s/.git" ] && _one "$s" "$PWD/$s"; done
  _one PARENT "$PWD"
  echo -e "  [$(hostname -s)] $mode: ${GRN}pushed=$P merged=$M pulled=$U${NC} noop=$N branch-held=$BH skipped=$SK push-unverified=$PU ${RED}CONFLICTS=$CF${NC}"
  for h in "${HELD[@]}"; do echo -e "     ${RED}X HELD $h${NC}"; done
  for u in "${UNVER[@]}"; do echo -e "     ${YLW}⚠ PUSH-UNVERIFIED $u (remote sha != local HEAD; re-check: git ls-remote origin main)${NC}"; done
  for b in "${BRANCH[@]}"; do echo -e "     ${YLW}B BRANCH-HELD $b (committed locally, NOT on main)${NC}"; done
  [ "$SK" -gt 0 ] && echo -e "     ${YLW}⤳ SKIPPED (live-edited, left untouched): ${SKIPPED[*]}${NC}"
  echo "     parent a/b vs origin/main: $(git rev-list --left-right --count HEAD...origin/main 2>/dev/null)"
  echo "     (WIP pinned to refs/fleet-sync/presync-$RUNTS in any repo that had uncommitted work — recover with: git show)"
  [ "$CF" -eq 0 ]
}

engine_state() {
  cd "$HOME/fleet" 2>/dev/null || return
  GIT_SSH_COMMAND="$GS" git fetch -q origin main 2>/dev/null
  local pb=$(git rev-list --count HEAD..origin/main 2>/dev/null) pa=$(git rev-list --count origin/main..HEAD 2>/dev/null)
  local subbeh=0 offmain=""
  for s in $(git config -f .gitmodules --get-regexp path 2>/dev/null | awk '{print $2}'); do
    [ -e "$s/.git" ] || continue
    GIT_SSH_COMMAND="$GS" git -C "$s" fetch -q origin main 2>/dev/null
    [ "$(git -C "$s" rev-list --count HEAD..origin/main 2>/dev/null)" -gt 0 ] && subbeh=$((subbeh+1))
    local br=$(git -C "$s" rev-parse --abbrev-ref HEAD 2>/dev/null); { [ "$br" != main ] && [ "$br" != HEAD ]; } && offmain="$offmain $s($br)"
  done
  echo "  [$(hostname -s)] parent ahead=$pa behind=$pb | subs-behind=$subbeh | off-main:[${offmain:- none}]"
}

# ───────────────────────────── orchestrator ─────────────────────────────
run_on() {  # $1 host, $2 subcmd
  local h="$1" c="$2"
  if [ "$h" = "$(hostname -s)" ]; then           # local host -> run engine directly
    [ "$c" = state ] && engine_state || engine "$c"
  else                                           # remote -> reachability (ssh -4, one retry), then pipe self
    ssh -4 -o ConnectTimeout=12 -o BatchMode=yes "$h" true 2>/dev/null \
      || ssh -4 -o ConnectTimeout=15 -o BatchMode=yes "$h" true 2>/dev/null \
      || { echo -e "  ${YLW}⤳ SKIP $h — unreachable (down)${NC}"; return 3; }
    ssh -4 -o ConnectTimeout=25 "$h" "SYNC_ALLOW_PUSH=${SYNC_ALLOW_PUSH:-0} bash -s -- $c --local" < "$SELF" \
      || echo -e "  ${YLW}⚠ $h — run dropped mid-op (flaky link); rerun 'fleet-sync $c --host $h'${NC}"
  fi
}

SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"; [ -f "$SELF" ] || SELF="$0"

if [ "$LOCAL" = 1 ]; then
  case "$CMD" in state) engine_state ;; push|converge) engine "$CMD" ;; sync) engine push; engine converge ;; *) echo "unknown: $CMD"; exit 2 ;; esac
  exit $?
fi

echo -e "${BLU}═══ fleet-sync $CMD  hosts=[$HOSTS]  $(date) ═══${NC}"
case "$CMD" in
  state)    for h in $HOSTS; do run_on "$h" state; done ;;
  push)     for h in $HOSTS; do echo -e "${BLU}── $h ──${NC}"; run_on "$h" push; done ;;
  converge) for h in $HOSTS; do echo -e "${BLU}── $h ──${NC}"; run_on "$h" converge; done ;;
  sync)     echo -e "${BLU}=== phase 1: push (commit+push all WIP) ===${NC}"; for h in $HOSTS; do echo -e "${BLU}── $h ──${NC}"; run_on "$h" push; done
            echo -e "${BLU}=== phase 2: converge (pull everyone to 0/0 — Rule 10) ===${NC}"; for h in $HOSTS; do echo -e "${BLU}── $h ──${NC}"; run_on "$h" converge; done ;;
  *) echo "usage: fleet-sync.sh <push|converge|sync|state> [--local|--hosts \"..\"|--host H]"; exit 2 ;;
esac
echo -e "${BLU}═══ fleet-sync $CMD done ═══${NC}"
