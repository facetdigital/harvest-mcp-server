# Plan: Dependency Hygiene Pass

## Execution Instructions

When executing this plan:

1. **Work step-by-step** - Complete each step fully before moving to the next
2. **Test-first within each step** - Write the failing test/check before the change
3. **Test after each step** - Run the test commands listed
4. **Commit after each step** - Use the provided commit message
5. **Update documentation continuously** - `readme.md`, `CLAUDE.md`, this file,
   `docs/plans/development-roadmap.md`
6. **Mark completion** - Move this item to "Completed" in the roadmap
7. **This is the one change that can break the server rather than extend it.**
   Do not combine it with feature work, and do not start it while any other
   branch of work is mid-flight. Step 4's live smoke test is the gate for
   calling it done.

---

## Summary

The dependency snapshot is a March 2025 lock: `mcp` 1.4.1 is many releases
behind and predates two SDK CVE fixes, `h11` 0.14.0 predates its
critical-rated CVE fix, and `certifi`'s CA bundle is stale. Meanwhile
`pyproject.toml` uses uncapped floors (`mcp>=1.4.1`, `httpx>=0.28.1`), so any
unfrozen resolve would jump `mcp` to the breaking 2.x line; only the
Dockerfile's `--frozen` flag keeps installs deterministic. The Dockerfile
itself pulls `python:3.12-slim-bookworm` by mutable tag and
`ghcr.io/astral-sh/uv:latest` unpinned, and `COPY . /code` with no
`.dockerignore` bakes the whole directory into image layers. This plan caps
the floors, refreshes the lock within those caps, pins the container inputs,
and proves the result against a live server before declaring success.

## Requirements

- **R1:** `pyproject.toml` carries explicit upper bounds: `mcp` capped below
  2.0; `httpx` capped at its current minor line (exact caps chosen at
  execution time after checking the then-current releases and changelogs).
- **R2:** `uv.lock` is refreshed within those caps; at minimum `h11` moves to
  0.16.0 or later, `mcp` to the newest 1.x, and `certifi` to a current
  bundle. All entries remain hash-pinned.
- **R3:** The full unit suite passes against the refreshed environment, and a
  live stdio round-trip works: server initializes, lists all tools, answers
  one read tool call, and still refuses writes under `HARVEST_READ_ONLY` and
  under an active `HARVEST_WRITE_TOOLS` allowlist.
- **R4:** Dockerfile base images are pinned by digest, the `uv` binary comes
  from a versioned (not `latest`) tag, and a `.dockerignore` excludes at
  least `.venv/`, `.git/`, `__pycache__/`, and any local env/config files.
- **R5:** Version alignment: `.python-version`, the Dockerfile's Python, and
  readme prerequisites agree (the readme's "Python 3.10 or higher" is wrong
  today; the code requires 3.11+).
- **R6:** Each concern lands as its own commit so any regression bisects to
  one change.

## Implementation Steps

### Step 1: Pin the smoke test before touching anything

- [ ] Write the (currently passing) test first: `tests/test_stdio_smoke.py`,
  stdlib unittest. Using the installed `mcp` client library over stdio to a
  subprocess of `harvest-mcp-server.py` with dummy credentials: initialize
  completes; `list_tools` returns the expected tool count (assert the exact
  number and spot-check names); calling `delete_time_entry` with
  `HARVEST_READ_ONLY=true` returns the `read_only_mode` payload. This is the
  regression net for the SDK bump, so it must pass BEFORE the bump: run it
  against the current environment and commit it green.
- [ ] Verify green against the current, pre-refresh environment.

**Satisfies:** R3 (the instrument for it)

**File(s):** `tests/test_stdio_smoke.py`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest tests.test_stdio_smoke -v
```

**Commit message:** `Add stdio smoke test pinning initialize, tool list, and refusals`

---

### Step 2: Cap the version floors

- [ ] Test-first: n/a (metadata only; Step 1's suite is the net).
- [ ] Implement: check current `mcp` 1.x latest and `httpx` releases; set
  `mcp>=1.4.1,<2` and an `httpx` cap matching its current minor line in
  `pyproject.toml`. Do NOT refresh the lock in this commit.
- [ ] Verify: `uv sync --frozen` still succeeds (lock untouched, caps
  compatible with pinned versions); full suite green.

**Satisfies:** R1, R6

**File(s):** `pyproject.toml`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv sync --frozen && uv run python -m unittest discover -s tests
```

**Commit message:** `Cap dependency version floors ahead of lock refresh`

---

### Step 3: Refresh the lock

- [ ] Test-first: n/a (Step 1's suite is the net).
- [ ] Implement: `uv lock --upgrade`, then review the lock diff by hand:
  every changed package, old and new version, all still hash-pinned from
  pypi.org. Confirm `h11` >= 0.16.0, `mcp` at newest 1.x, `certifi` current.
  Any surprising new package in the tree is a stop-and-investigate.
- [ ] Verify: `uv sync` then the FULL suite including the stdio smoke test.
  If the smoke test fails, the SDK changed behavior the server depends on:
  fix forward if small, or pin `mcp` tighter and record why.

**Satisfies:** R2, R3, R6

**File(s):** `uv.lock`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv sync && uv run python -m unittest discover -s tests -v
```

**Commit message:** `Refresh dependency lock within capped floors`

---

### Step 4: Live verification against real Harvest

- [ ] Test-first: n/a (manual gate; the checklist below defines done).
- [ ] Verify with real credentials in a real MCP session: server connects,
  a read tool returns live data, write tools refuse under the global
  read-only config, and (in a scratch session with the allowlist set and
  read-only unset, using deliberately invalid credentials) a non-allowlisted
  write returns `write_not_allowed` without reaching the network.
- [ ] Implement: fix anything the live pass surfaces; each fix is its own
  commit.

**Satisfies:** R3

**File(s):** whatever the run exposes

**Test:**
```bash
# in a live session: one read call, one refused write, per above
```

**Commit message:** none unless fixes are needed

---

### Step 5: Container pinning

- [ ] Test-first: n/a (build verification below).
- [ ] Implement: pin `python:3.12-slim-bookworm` by digest; replace
  `ghcr.io/astral-sh/uv:latest` with a versioned tag pinned by digest; add
  `.dockerignore` covering `.venv/`, `.git/`, `__pycache__/`, `*.pyc`,
  `.claude/`, and local env files.
- [ ] Verify: `docker build .` succeeds and the image runs the server
  (`docker run` with dummy env vars reaches the missing-credentials or
  startup path as expected). Skip gracefully if Docker is unavailable
  locally, and say so rather than claiming verification.

**Satisfies:** R4, R6

**File(s):** `Dockerfile`, `.dockerignore`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
docker build -t harvest-mcp-test . && docker run --rm -e HARVEST_ACCOUNT_ID=x -e HARVEST_API_KEY=x harvest-mcp-test --help 2>&1 | head -5
```

**Commit message:** `Pin container inputs by digest and add .dockerignore`

---

### Step 6: Version alignment and docs

- [ ] Test-first: n/a (documentation).
- [ ] Implement: align `.python-version`, Dockerfile Python, and the readme's
  prerequisites (readme currently claims 3.10+; the union type syntax and
  `requires-python` floor need 3.11+). Update readme/CLAUDE.md to note the
  capped floors and that lock refreshes are deliberate, reviewed events.
- [ ] Verify: proofread; no emdashes; suite green one last time.

**Satisfies:** R5

**File(s):** `readme.md`, `CLAUDE.md`, `.python-version` (if changed),
`Dockerfile` (if changed)

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest discover -s tests
```

**Commit message:** `Align Python version claims and document dependency policy`

---

## Files Modified (Summary)

| File | Steps |
|------|-------|
| `tests/test_stdio_smoke.py` | 1 |
| `pyproject.toml` | 2 |
| `uv.lock` | 3 |
| `Dockerfile` | 5, 6 |
| `.dockerignore` | 5 |
| `readme.md` | 6 |
| `CLAUDE.md` | 6 |

## Notes

- **Upstream consideration:** the floor caps, lock refresh, Docker pinning,
  and readme version fix are all upstreamable and benefit the upstream repo
  (its lock carries the same stale pins). Decide at execution time whether to
  include them in an upstream PR after this lands and proves stable here.
- **MCP tool annotations depend on this plan**: they need an SDK newer than
  1.4.1, so `docs/plans/mcp-tool-annotations.md` executes only after Step 3
  lands and Step 4 passes.
