# SEGA Sysnc Module - Multi-System Git Synchronization

**Cross-host git sync for the FLEET fleet: every submodule plus the parent repo, per host.**

> 📓 **Before running any sync, read the Standing Rules in the [Fleet Sync Journal](../../../../../common/docs/process/SYNC_JOURNAL.md); append a run entry after.** The journal's rules override script defaults.

Policy (do not weaken): **commit, never stash** (a stash can be stranded; a commit can't) · **push-first** · **never auto-resolve a content conflict** (abort + hold + report) · one host at a time, in the foreground, with per-repo visibility.

---

## START HERE: the canonical per-host cycle

### 1. `bulk-commit-pull-push.sh`: integrate live WIP

Per repo (every submodule + parent), push-first:

1. `git add -A && commit`. WIP becomes a real commit; `.env` is committed like any other file (operator directive, see the journal).
2. `git push origin HEAD:main` FIRST. If the remote hasn't moved, this lands with no merge commit.
3. Only on a non-fast-forward reject: `fetch` + `merge origin/main`, then push again. A content conflict means `git merge --abort` + HOLD + report, never auto-resolved; the WIP stays committed.

Notes (verified against the script):
- Forces `ssh -4` (node-1's IPv6 route to gitlab flakes). A "successful" push that doesn't land is the tell; check `git ls-remote origin main`.
- No exclusions by default. Skip a repo deliberately via `SKIP_REPOS="atlas ..."`.
- Branch guard: never pushes a named non-main branch to main, and the parent keeps its recorded origin/main gitlink for a branch-held submodule (no dangling pointer).

```bash
./bulk-commit-pull-push.sh [host_label] [commit_message]
```

### 2. `bulk-pull.sh`: converge, verifying from the pull direction

Non-stash pull of `origin/main` into every repo. Per repo it reports **UPDATED** / **CONFLICT** (merge aborted, WIP untouched) / **BLOCKED** (dirty overlap with incoming; commit first with step 1, then re-pull) / up-to-date. Never stashes, never commits, never pushes, never discards. Also forces `ssh -4`.

```bash
./bulk-pull.sh [host_label]
```

Run the cycle host by host until every host reports clean.

---

## `fleet-sync.sh`: consolidated tool, single-host use only

Consolidates `push` / `converge` / `state` into one tool. **Multi-host orchestration is NOT approved** (operator directive 2026-08-07): the default host list, or `--hosts` with more than one entry, HARD-REFUSES unless you pass `--i-approve-multihost` explicitly. The multi-host cycle chases a moving target (a live repo keeps advancing on one host) and masked per-host realities (full disks, down minis) behind a summary line. Use `--host <H>` or `--local`, one host at a time.

```bash
./fleet-sync.sh state --host node-1     # read-only: parent + submodule ahead/behind vs origin/main
./fleet-sync.sh push --local             # per-host push engine (commit -> push-first -> merge on reject)
./fleet-sync.sh converge --local         # per-host pull-down + push-if-ahead
```

Safeguards (in the script): `FLEET_SKIP="repo ..."` or a `.fleet-sync-skip` file leaves a live-edited repo untouched; pre-sync WIP is pinned to a durable ref `refs/fleet-sync/presync-<ts>`; only submodule-gitlink conflicts auto-advance (to the sub's origin/main tip), content conflicts always hold.

---

## Utility scripts (current)

- `convert-dir-to-submodule.sh` / `receive-submodule-conversion.sh`: convert a parent-tracked directory into a submodule and receive that conversion on other hosts (used for the 2026-07-09 conversions).
- `setup-gitlab-secrets.sh`: GitLab CI/CD secrets setup.
- `sync-cleaned-history.sh`: propagate a history rewrite.

---

## DEPRECATED / superseded scripts (kept for history, do not use)

| Script(s) | Status |
|---|---|
| `bulk-stash-pull-pop-push.sh` | **DEPRECATED.** Stash-based: it stashes every dirty file before pulling. A stash that isn't popped strands WIP invisibly (verifying commits/pushes does not catch it). Policy is commit, never stash; use `bulk-commit-pull-push.sh`. If a past run left a stash, see "Stranded-stash recovery" below. |
| `gitlab-bulk-push.sh` / `gitlab-bulk-pull.sh` / `gitlab-verify-sync.sh` | Superseded by the cycle above. The pull auto-stashes (hides overlaps); the verify targets the retired EC2 topology. |
| `gitlab-bulk-{push,pull}-projects{1,2,3}.sh` | Dead. Hardcoded per-EC2-instance project groups, written for `/home/testuser/fleet` on the retired EC2 instances. |
| `gitlab-bulk-branch-push.sh` | Dead. Branch-based workflow that resolves conflicts automatically, which violates the never-auto-resolve rule; fleet work happens on main. |
| `consolidate-with-submodules.sh` / `option-b-consolidation.sh` / `inspect-ec2-changes.sh` / `inspect-ec2-changes-enhanced.sh` / `analyze-3way-conflicts.py` / `sync-claude-settings-to-ec2.sh` | EC2-era: built for the retired 3-EC2 topology (Local + Instance 1 + Instance 2, IPs/SSH key from `SYSMON_INSTANCE*_IP` / `SYSMON_SSH_KEY` or `[instances]` in `config/sega.toml`). That topology is retired (see `dispatcher/BRAIN.md` §8); historical reference only. |

### Stranded-stash recovery (after any legacy stash-script run)

1. Check every host, even after a "finished" run: `git stash list | grep -E 'main-post-submodule-update|pre-consolidation'`. A same-day stash on a finished run is un-restored WIP.
2. Never blind `git stash pop` over a live tree. List stashed files (`git stash show stash@{0} --name-only`), classify vs the current tree (missing = safe to restore, identical = skip, git-modified = an operator's live edit, leave it, differs-but-clean = safe), `cp`-backup anything you overwrite, restore only the safe set with `git checkout stash@{0} -- <files>`, verify by hash, and **never drop the stash** (it may hold other operators' parallel work).

---

## Related

- [`common/docs/process/FLEET_OPERATIONS.md`](../../../../../common/docs/process/FLEET_OPERATIONS.md) - task-indexed fleet-ops runbook
- [Preserve Module](../preserve/README.md) - backup before sync
- [Sysmon Module](../sysmon/README.md) - system monitoring
- [SEGA CLI Reference](/sega/docs/reference/cli-reference.md)

---

*For questions or improvements, update this README.*
