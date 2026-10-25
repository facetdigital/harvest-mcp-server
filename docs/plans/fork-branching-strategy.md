# Plan: Fork Branching Strategy (GitFlow-like)

## Execution Instructions

When executing this plan:

1. **Work step-by-step** - Complete each step fully before moving to the next
2. **Test-first within each step** - Write the failing test/scenario before the implementation, then make it pass
3. **Test after each step** - Run the test commands listed to verify the change works
4. **Commit after each step** - Use the provided commit message for each step
5. **Update documentation continuously** - After ANY change that affects them, update:
   - `readme.md` - User-facing documentation (upstreamable; keep fork-neutral)
   - `CLAUDE.md` - Fork operating notes
   - `docs/plans/fork-branching-strategy.md` - Mark progress, update status
   - `docs/plans/development-roadmap.md` - Mark progress, update status
6. **Mark completion** - When all steps are done, move this item to "Completed" in the roadmap
7. **Stop at HUMAN GATE steps** - Steps 3 and 6 carry a `HUMAN GATE` marker.
   An autonomous runner MUST halt before them and report that Scott is needed:
   Step 3 force-pushes a rewritten `main` to the public fork and disposes of
   draft PR #2; Step 6 opens a PR on the maintainer's repo. Both are
   outward-facing and irreversible in spirit.
8. **Sequencing:** this plan executes AFTER the roadmap's "Live validation of
   the new time-entry write tools" item, per Scott's call on 2026-08-07.

---

## Summary

Replace the ad hoc "run from a feature branch and remember what to exclude"
arrangement with a durable three-tier branch model:

- **`main`**: a pure mirror of `upstream/main`. Sync-only; never committed to
  directly. Kept exactly equal to upstream's SHAs (`--ff-only`).
- **`facet`**: the fork's long-lived operating branch. Carries everything ours:
  fork-internal docs (CLAUDE.md, docs/plans/, bin/) plus feature work, both
  upstreamable and private. The live MCP server runs from this branch. Absorbs
  upstream via `main` merges.
- **`feature/*`**: short-lived branches off `facet`, merged back to `facet`.
- **`upstream-pr/*`**: throwaway branches cut from `main`, populated by
  cherry-picking ONLY upstreamable code commits, verified clean by a committed
  check script, then pushed and PR'd to taiste. Never merged locally; deleted
  after upstream resolves them.

Two committed helper scripts make the model mechanical rather than
disciplinary: `bin/check-upstream-clean` (fails when an upstream-bound branch
touches fork-internal paths) and `bin/make-upstream-branch` (builds an
`upstream-pr/*` branch from named commits and runs the check).

## Requirements

- **R1:** `main` is bit-identical to `upstream/main` after every sync; no fork
  commit ever lands on it.
- **R2:** The server keeps running from one stable branch (`facet`) across
  upstream syncs, with no history rewrites on it (merge-based, no force-push).
- **R3:** Fork-internal paths (`CLAUDE.md`, `docs/plans/`, `bin/`,
  `.claude/`) are structurally prevented from reaching an upstream PR: a
  committed script fails loudly, and the upstream-branch builder runs it
  automatically.
- **R4:** The upstream submission recipe is executable, not prose: one command
  builds a verified `upstream-pr/*` branch from a list of commits.
- **R5:** The model is documented in CLAUDE.md well enough that a cold session
  can sync upstream, cut a feature, and build an upstream PR without asking.
- **R6:** The transition preserves current state: draft PR #2's content stays
  safekept (in `facet` on origin), and the running server never points at a
  deleted branch.

## Implementation Steps

### Step 1: The never-leak check script

- [ ] Write the failing test first: `tests/test_fork_hygiene.py` (stdlib
  unittest, consistent with the existing suite). In a scratch git repo built
  under the test's temp dir: a branch whose diff against a base ref touches
  `CLAUDE.md` and `docs/plans/x.md` makes the script exit non-zero and print
  both offending paths; a branch touching only `harvest-mcp-server.py`,
  `tests/`, `readme.md`, and `.gitignore` exits zero; a branch touching
  `bin/anything` fails; the script fails with a usage message when given no
  branch. Expected to FAIL (script does not exist).
- [ ] Implement: `bin/check-upstream-clean <branch> [--base <ref>]` (bash).
  Default base: `upstream/main` if that remote ref exists, else `--base` is
  required (tests use `--base`). Diffs `base...branch`, matches changed paths
  against the fork-internal list hardcoded in the script (`CLAUDE.md`,
  `docs/plans/`, `bin/`, `.claude/`), prints offenders with a FAIL banner and
  exits 1, or prints OK and exits 0. Executable bit set.
- [ ] Verify green: hygiene tests pass; then run it for real against
  `feature/time-entry-write-tools` with `--base upstream/main` and confirm it
  FAILS naming exactly `CLAUDE.md` and the two `docs/plans/` files (proving it
  catches today's actual state).

**Satisfies:** R3; roadmap "GitFlow-like branching strategy" item

**File(s):** `bin/check-upstream-clean`, `tests/test_fork_hygiene.py`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest tests.test_fork_hygiene -v
bin/check-upstream-clean feature/time-entry-write-tools --base upstream/main; echo "exit: $?"   # expect FAIL, exit 1
```

**Commit message:** `Add check-upstream-clean to gate upstream-bound branches`

---

### Step 2: The upstream-branch builder

- [ ] Write the failing test first: extend `tests/test_fork_hygiene.py`. In
  the scratch repo: given a base ref and two commit SHAs, the builder creates
  the named branch at base, cherry-picks the SHAs in order, runs the check
  script, and exits 0 with the branch left checked out in a detached-safe way
  (test asserts branch exists, contains both patches, and working branch of
  the main worktree is unchanged); when one cherry-picked commit touches a
  fork-internal path, the builder aborts, deletes the partial branch, and
  exits non-zero. Expected to FAIL.
- [ ] Implement: `bin/make-upstream-branch <branch-name> <commit>...`
  (bash). Uses a temporary worktree (`git worktree add`) so the operating
  checkout never moves; cuts `<branch-name>` from `upstream/main` (or
  `--base <ref>` for tests), cherry-picks the listed commits, runs
  `bin/check-upstream-clean`, and on any failure removes the worktree and the
  partial branch before exiting non-zero. Prints the push and PR commands to
  run next, but never pushes.
- [ ] Verify green: hygiene tests pass.

**Satisfies:** R3, R4

**File(s):** `bin/make-upstream-branch`, `tests/test_fork_hygiene.py`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest tests.test_fork_hygiene -v
```

**Commit message:** `Add make-upstream-branch to build verified upstream PR branches`

---

### Step 3: Branch surgery: create facet, mirror main

> **HUMAN GATE. Do not execute autonomously.** This force-pushes a rewritten
> `main` to the public fork and disposes of draft PR #2. Scott confirms each
> action.

- [ ] Test-first: n/a (branch operations; verification commands below define
  done).
- [ ] Implement: create `facet` at the current tip of
  `feature/time-entry-write-tools` and push it:
  `git branch facet && git push -u origin facet`. Check out `facet` in this
  working copy so the server now runs from it (R2, R6).
- [ ] Implement: make `main` a pure mirror: `git fetch upstream`,
  `git checkout main`, `git reset --hard upstream/main`,
  `git push --force-with-lease origin main`. This drops the fork-local merge
  commit `3c3f4fe` from `main` (its tree is preserved in `facet`'s history),
  making fork `main` SHA-identical to upstream (R1). Return to `facet`.
- [ ] Implement: dispose of draft PR #2 with Scott: either close it with a
  comment noting the work now lives on `facet` (safekeeping preserved by the
  pushed branch), or retarget its base if keeping a fork-internal review
  surface is wanted. Then delete `feature/time-entry-write-tools` locally and
  on origin; its commits are all reachable from `facet`, and the five
  upstreamable SHAs are recorded in Step 6.
- [ ] Verify: `git rev-parse main upstream/main` prints the same SHA twice;
  `git branch --show-current` prints `facet`; the MCP server still starts
  from this directory (run the unit suite as a smoke check).

**Satisfies:** R1, R2, R6

**File(s):** none (branch operations only)

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
git fetch upstream && git rev-parse main upstream/main   # identical SHAs
git branch --show-current                                 # facet
uv run python -m unittest discover -s tests               # still green
```

**Commit message:** none (no commits in this step)

---

### Step 4: Document the model in CLAUDE.md

- [ ] Test-first: n/a (documentation).
- [ ] Implement: rewrite CLAUDE.md's operating-state section as the branch
  model: the three tiers and their rules; the sync recipe
  (`git fetch upstream && git checkout main && git merge --ff-only
  upstream/main && git push && git checkout facet && git merge main`, then run
  the test suite per the existing convention); the feature recipe (branch from
  `facet`, merge back to `facet`); the upstream recipe (run
  `bin/make-upstream-branch`, then push and `gh pr create --repo
  taiste/harvest-mcp-server` by hand); and the standing rule that `main` is
  never committed to directly.
- [ ] Implement: remove the now-obsolete "runs from feature branch as if
  main" language here and in the roadmap; the operating branch is `facet`.
- [ ] Verify: proofread; no emdashes; every command in the doc actually runs.

**Satisfies:** R5

**File(s):** `CLAUDE.md`, `docs/plans/development-roadmap.md`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
grep -c 'facet' CLAUDE.md            # >= several
grep -c '—' CLAUDE.md || true        # expect 0 in new content
```

**Commit message:** `Document the mirror-main plus facet branch model`

---

### Step 5: Prove the loop: dry-run an upstream sync

- [ ] Test-first: n/a (process rehearsal; the assertions below define done).
- [ ] Implement: run the documented sync recipe end to end against the real
  upstream (fetch, ff-only merge into `main`, merge `main` into `facet`). If
  upstream has not moved since `3c3f4fe`'s parents, this is a no-op pass that
  still proves the commands are correct; if upstream HAS moved, this is the
  first real sync, and the post-merge test run is the guard-coverage check
  earning its keep.
- [ ] Verify: `main` equals `upstream/main`; `facet` contains it; suite green.

**Satisfies:** R1, R2, R5

**File(s):** none

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
git rev-parse main upstream/main                      # identical
git merge-base --is-ancestor main facet && echo ok    # ok
uv run python -m unittest discover -s tests           # green
```

**Commit message:** none (merge commits only, if upstream moved)

---

### Step 6: Build the real upstream PR branch

> **HUMAN GATE at the end. Do not open the upstream PR autonomously.**
> Building and verifying the branch locally is fine; pushing it and opening
> the PR on taiste/harvest-mcp-server is Scott's trigger.

- [ ] Test-first: n/a (uses the tested tooling from Steps 1 and 2).
- [ ] Implement: `bin/make-upstream-branch upstream-pr/time-entry-write-tools
  62965bb 3a0324d 135e54c 8d0fb88 a91164e` (the five upstreamable commits:
  tools+gating, tests, readme, gitignore, test hardening; CLAUDE.md and
  docs/plans commits excluded by construction).
- [ ] Verify: `bin/check-upstream-clean upstream-pr/time-entry-write-tools`
  passes; `uv run python -m unittest discover -s tests` is green on that
  branch (run in the temp worktree); diff against `upstream/main` shows only
  the four expected files.
- [ ] STOP and report: hand Scott the ready branch plus the exact
  `git push` and `gh pr create --repo taiste/harvest-mcp-server` commands
  with a drafted, generic PR description. Scott submits (or edits first).

**Satisfies:** R3, R4; CLAUDE.md "Next steps" item 1; roadmap "Upstream
submission and sync"

**File(s):** none new

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
bin/check-upstream-clean upstream-pr/time-entry-write-tools; echo "exit: $?"   # OK, 0
git diff --stat upstream/main..upstream-pr/time-entry-write-tools              # 4 files
```

**Commit message:** none (branch construction only)

---

## Files Modified (Summary)

| File | Steps |
|------|-------|
| `bin/check-upstream-clean` | 1 |
| `bin/make-upstream-branch` | 2 |
| `tests/test_fork_hygiene.py` | 1, 2 |
| `CLAUDE.md` | 4 |
| `docs/plans/development-roadmap.md` | 4 |
| branch topology (no files) | 3, 5, 6 |

## Notes and Known Limitations

- **`facet` never force-pushes; `main` force-pushes exactly once** (Step 3's
  mirror reset). After that, `main` moves only by `--ff-only` merges, so
  `--force-with-lease` should never be needed again. If it ever is, upstream
  rewrote history and that deserves a human look, not an automatic push.
- **The check script's path list is the single source of truth for "fork
  internal".** Adding a new private path means adding it there (and the test
  proves the script catches it). The list intentionally includes `bin/`
  itself, so the tooling can never leak into an upstream PR either.
- **`tests/` is deliberately upstreamable.** The suite was written
  dependency-free partly so it can ride along to upstream, where it becomes
  the repo's first tests.
- **Draft PR #2 stops being the safekeeping mechanism** once `facet` is
  pushed; the branch on origin is. Its disposition is a Step 3 human-gate
  decision, not assumed.
