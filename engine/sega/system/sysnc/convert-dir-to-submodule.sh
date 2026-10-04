#!/bin/bash
# Convert a parent-tracked project DIRECTORY into a git SUBMODULE (converting side — run on ONE host).
#
#   Per project P:
#     1. create private gitlab repo <group>/P.git (idempotent — skip if exists)
#     2. capture P's EXACT parent-tracked file list (git ls-files) — NOT add -A (no node_modules/build junk)
#     3. git rm -r --cached P  (untrack in parent, keep all files on disk)
#     4. init P as its own repo, add exactly the tracked files, commit, push to the new remote
#     5. git submodule add --force <url> P  (register .gitmodules + gitlink)
#
# Seeds faithfully = new submodule tree == the monorepo's tracked tree for P (incl. any already-tracked
# .env — same as today, not worse). Working-dir untracked (.env edits, node_modules) stays on disk.
#
# After running for all projects, COMMIT the parent (.gitmodules + gitlinks) and push — then run the
# receiving-side migration on the OTHER hosts (receive-submodule-conversion.sh).
#
# Usage:  ./convert-dir-to-submodule.sh <project> [<project> ...]
# Requires: keys/.gitlab_token (PAT with api scope). Run from ~/fleet.

set -o pipefail
cd "$HOME/fleet" 2>/dev/null || { echo "ERROR: ~/fleet not found"; exit 1; }
TOK=$(cat keys/.gitlab_token 2>/dev/null)
[ -n "$TOK" ] || { echo "ERROR: keys/.gitlab_token missing"; exit 1; }
GROUP_ID=110131361
GROUP=example-org-group
API=https://gitlab.com/api/v4
# Force IPv4: some hosts (e.g. node-1) have a flaky IPv6 route to gitlab that silently drops pushes.
GS='ssh -4 -o ConnectTimeout=25'

for P in "$@"; do
  echo "════════ convert: $P ════════"
  [ -d "$P" ] || { echo "  ✗ $P: not a directory — skip"; continue; }
  git ls-files --error-unmatch -- "$P" >/dev/null 2>&1 || { echo "  ✗ $P: not parent-tracked — skip"; continue; }
  URL="git@gitlab.com:$GROUP/$P.git"

  # 1. create repo (idempotent)
  exists=$(curl -s -o /dev/null -w '%{http_code}' --header "PRIVATE-TOKEN: $TOK" "$API/projects/$GROUP%2F$P")
  if [ "$exists" = 200 ]; then
    echo "  • repo exists on gitlab (reuse)"
  else
    code=$(curl -s -o /tmp/mk_$P.json -w '%{http_code}' --request POST --header "PRIVATE-TOKEN: $TOK" \
      "$API/projects" --data "name=$P" --data "path=$P" --data "namespace_id=$GROUP_ID" --data "visibility=private")
    if echo "$code" | grep -qE '20[01]'; then echo "  ✓ repo created"; else echo "  ✗ repo create HTTP $code: $(cat /tmp/mk_$P.json | head -c 200)"; continue; fi
  fi

  # 2. capture the EXACT parent-tracked tree object (faithful — every tracked file incl .env; no
  #    disk .env mods, no untracked junk, no .gitignore drops). commit-tree seeds from this exactly.
  seedsha=$(git rev-parse --short HEAD)
  TREE=$(git rev-parse "HEAD:$P")
  n=$(git ls-tree -r "$TREE" 2>/dev/null | wc -l | tr -d ' ')
  echo "  • faithful tracked tree $(echo $TREE|cut -c1-9): $n files (from parent $seedsha)"

  # 3. untrack in parent (keep all files on disk)
  git rm -r --cached --quiet "$P"

  # 4. seed the new repo from the exact tree object (initial push to empty repo's main = no force)
  SEED=$(git commit-tree "$TREE" -m "seed $P from fleet monorepo (faithful tracked tree @ $seedsha)")
  git update-ref "refs/heads/_seed_$P" "$SEED"
  GIT_SSH_COMMAND="$GS" git push "$URL" "refs/heads/_seed_$P:refs/heads/main" >/tmp/seedpush_$P.log 2>&1 \
    && echo "    push: $(GIT_SSH_COMMAND="$GS" git ls-remote "$URL" refs/heads/main 2>/dev/null | cut -c1-12)" \
    || echo "    push FAILED: $(tail -1 /tmp/seedpush_$P.log)"
  git update-ref -d "refs/heads/_seed_$P"

  # 5. materialize P/ as a submodule checkout of the seed WITHOUT touching disk (host-local .env mods stay)
  rm -rf "$P/.git" 2>/dev/null
  ( cd "$P"; git init -q; git remote add origin "$URL" 2>/dev/null; GIT_SSH_COMMAND="$GS" git fetch -q origin 2>/dev/null
    git update-ref refs/heads/main "$SEED"; git symbolic-ref HEAD refs/heads/main; git reset --mixed -q )
  GIT_SSH_COMMAND="$GS" git submodule add --force "$URL" "$P" >/tmp/subadd_$P.log 2>&1 || echo "    submodule add note: $(tail -1 /tmp/subadd_$P.log)"

  # faithfulness assertion
  got=$(git -C "$P" rev-parse 'HEAD^{tree}' 2>/dev/null)
  [ "$got" = "$TREE" ] && echo "    ✓ FAITHFUL: submodule tree == parent tracked tree" || echo "    ✗ MISMATCH: $got != $TREE — INVESTIGATE"
  gl=$(git ls-files --stage -- "$P" 2>/dev/null | grep -q '^160000' && echo yes || echo no)
  inmod=$(git config -f .gitmodules --get "submodule.$P.url" 2>/dev/null)
  echo "  ✓ $P: gitlink-staged=$gl  .gitmodules-url=${inmod:-MISSING}  submodule-HEAD=$(git -C "$P" rev-parse --short HEAD 2>/dev/null)"
done
echo ""
echo "NEXT: review, then commit parent (.gitmodules + gitlinks) and push; then run receiving migration on other hosts."
