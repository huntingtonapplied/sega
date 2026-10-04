#!/bin/bash
# Receiving-side migration: transition project DIRECTORIES that just became SUBMODULES on origin,
# on a host that still has them as plain tracked dirs. A normal pull would collide (tree→gitlink).
#
# PHASED (the single FF converts ALL passed projects at once, so all must be moved aside first):
#   1. backup + move ALL passed projects aside (cp -a → ~/premigration-…; then mv out of worktree)
#   2. one FF parent → origin/main  (all become gitlinks; paths are free so no collision)
#   3. git submodule update --init  each project (clones into the empty paths)
#   4. verify each submodule commit == the parent gitlink, then restore host-local .env* from backup
#   backup LEFT in place — never auto-deleted.
#
# Usage:  ./receive-submodule-conversion.sh <project> [<project> ...]

set -o pipefail
cd "$HOME/fleet" 2>/dev/null || { echo "ERROR: ~/fleet not found"; exit 1; }
GS='ssh -4 -o ConnectTimeout=25'
GIT_SSH_COMMAND="$GS" git fetch -q origin 2>/dev/null
BACKUP="$HOME/premigration-submodules-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"
fail=0; TODO=()

# ---- pre-flight: which projects actually need converting here ----
for P in "$@"; do
  if [ "$(git ls-tree HEAD -- "$P" 2>/dev/null | awk '{print $1}')" = 160000 ] && [ -f "$P/.git" ]; then
    echo "• $P already a submodule — skip"; continue; fi
  if [ "$(git ls-tree origin/main -- "$P" 2>/dev/null | awk '{print $1}')" != 160000 ]; then
    echo "✗ $P not a gitlink on origin/main — skip (convert on source host first)"; fail=1; continue; fi
  [ -d "$P" ] || { echo "✗ $P absent on disk — skip"; fail=1; continue; }
  TODO+=("$P")
done
[ "${#TODO[@]}" -eq 0 ] && { echo "nothing to migrate"; exit $fail; }
echo "→ migrating: ${TODO[*]}"

# ---- phase 1: backup + move ALL aside ----
for P in "${TODO[@]}"; do
  cp -a "$P" "$BACKUP/$P" && echo "  backed up $P ($(find "$BACKUP/$P" -type f | wc -l | tr -d ' ') files)"
  mv "$P" "$BACKUP/.$P.moved"
done

# ---- phase 2: single FF (all paths free → tree→gitlink applies cleanly) ----
if git merge --ff-only origin/main >/tmp/recvff.log 2>&1; then
  echo "  ✓ FF → $(git rev-parse --short HEAD)"
else
  echo "  ✗ FF blocked: $(tail -2 /tmp/recvff.log | tr '\n' ' ')"
  echo "  restoring all moved dirs (no changes made):"
  for P in "${TODO[@]}"; do mv "$BACKUP/.$P.moved" "$P"; done
  echo "  backup at $BACKUP"; exit 1
fi

# ---- phase 3: clone submodules ----
for P in "${TODO[@]}"; do
  GIT_SSH_COMMAND="$GS" git submodule update --init "$P" >/tmp/recvsub_$P.log 2>&1 || echo "  ⚠ $P submodule update: $(tail -1 /tmp/recvsub_$P.log)"
done

# ---- phase 4: verify + restore .env ----
for P in "${TODO[@]}"; do
  want=$(git ls-tree HEAD -- "$P" | awk '{print $3}')
  got=$(git -C "$P" rev-parse HEAD 2>/dev/null)
  if [ "$want" = "$got" ]; then vok="✓ $(echo $got|cut -c1-9)"; else vok="✗ want=$(echo $want|cut -c1-9) got=$(echo $got|cut -c1-9)"; fail=1; fi
  restored=0
  while IFS= read -r f; do
    rel="${f#$BACKUP/$P/}"; mkdir -p "$P/$(dirname "$rel")" 2>/dev/null; cp -a "$f" "$P/$rel" 2>/dev/null && restored=$((restored+1))
  done < <(find "$BACKUP/$P" \( -name '.env' -o -name '.env.*' \) 2>/dev/null)
  echo "  $P: $vok  files=$(git -C "$P" ls-files|wc -l|tr -d ' ')  .env-restored=$restored"
done

echo ""
echo "backup retained: $BACKUP  (remove manually once verified)"
echo "parent HEAD: $(git rev-parse --short HEAD)  origin/main: $(git rev-parse --short origin/main)"
[ "$fail" -eq 0 ] && echo "RESULT: OK" || echo "RESULT: attention needed (see above)"
