# Plan: MCP Tool Annotations

## Execution Instructions

When executing this plan:

1. **Work step-by-step** - Complete each step fully before moving to the next
2. **Test-first within each step** - Write the failing test before the implementation
3. **Test after each step** - Run the test commands listed
4. **Commit after each step** - Use the provided commit message
5. **Update documentation continuously** - `readme.md`, `CLAUDE.md`, this file,
   `docs/plans/development-roadmap.md`
6. **Mark completion** - Move this item to "Completed" in the roadmap
7. **Hard dependency:** `docs/plans/dependency-hygiene.md` must be fully
   complete first. The pinned mcp 1.4.1 predates tool annotations; do not
   start this plan until the refreshed SDK is live-verified.

---

## Summary

No tool declares MCP annotations today, so a client cannot programmatically
distinguish `delete_project` (cascades to every time entry and expense on the
project) from `list_clients`. Once the SDK bump lands, annotate all tools
with `readOnlyHint` / `destructiveHint` / `idempotentHint`, derived from the
same source of truth the guards use (`WRITE_TOOLS` plus a new
`DESTRUCTIVE_TOOLS` set), with a structural test asserting code and
annotations can never disagree.

## Requirements

- **R1:** Every tool carries annotations: `readOnlyHint=True` exactly for
  tools not in `WRITE_TOOLS`; `destructiveHint=True` exactly for tools in a
  new `DESTRUCTIVE_TOOLS` set.
- **R2:** `DESTRUCTIVE_TOOLS` = the four delete tools plus
  `send_estimate_message` (external email is irreversible in the way that
  matters). Rationale recorded in a comment; membership changes are a
  reviewed decision, not a drive-by.
- **R3:** Annotations are verified structurally: a test derives the expected
  annotation for every registered tool from `WRITE_TOOLS` /
  `DESTRUCTIVE_TOOLS` and fails on any mismatch or any unannotated tool, so
  a future tool cannot ship without correct annotations.
- **R4:** Annotations are visible to a real client: the stdio smoke test
  asserts they arrive in `list_tools` results.
- **R5:** No behavioral change to any tool: annotations are hints for
  clients; guards and allowlist behavior are untouched.

## Implementation Steps

### Step 1: Confirm SDK surface and pin expectations

- [ ] Test-first: n/a for this step (investigation); its output is the exact
  annotation API for the SDK version now pinned (decorator parameter name
  and annotation model fields).
- [ ] Implement: verify with the installed SDK that `@mcp.tool()` accepts
  annotations and how they serialize through `list_tools`. Record the exact
  form in this plan file before proceeding.
- [ ] Verify: a one-tool spike on a scratch branch shows annotations arriving
  through a stdio client round trip.

**Satisfies:** prerequisite for R1 through R4

**File(s):** this plan file (recorded findings)

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -c "import mcp; print(mcp.__version__ if hasattr(mcp,'__version__') else 'check dist metadata')"
```

**Commit message:** `Record annotation API surface for the pinned SDK` (plan-file update only)

---

### Step 2: DESTRUCTIVE_TOOLS and the structural test

- [ ] Write the failing test first, in `tests/test_write_tools.py` (or a new
  `tests/test_annotations.py`): every registered tool has annotations;
  `readOnlyHint` is true exactly for non-`WRITE_TOOLS` tools;
  `destructiveHint` is true exactly for `DESTRUCTIVE_TOOLS`; every name in
  `DESTRUCTIVE_TOOLS` is also in `WRITE_TOOLS`. Expected to FAIL (no
  annotations exist).
- [ ] Implement: add `DESTRUCTIVE_TOOLS` frozenset (`delete_project`,
  `delete_task_assignment`, `delete_user_assignment`, `delete_estimate`,
  `send_estimate_message`) with the R2 rationale comment.
- [ ] Verify: the membership assertions pass; the per-tool annotation
  assertions still fail (annotations land in Step 3).

**Satisfies:** R2, R3

**File(s):** `harvest-mcp-server.py`, `tests/test_annotations.py`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest tests.test_annotations -v   # membership green, annotations red
```

**Commit message:** `Define DESTRUCTIVE_TOOLS with structural expectations`

---

### Step 3: Annotate all tools

- [ ] Test-first: already written (Step 2's failing assertions).
- [ ] Implement: add annotations to every `@mcp.tool()` decorator, derived
  mechanically from the two sets (a scripted transform keyed on the function
  name is acceptable; review the full diff). Read tools additionally get
  `idempotentHint=True` where accurate.
- [ ] Verify green: full suite passes, including the structural test.

**Satisfies:** R1, R5

**File(s):** `harvest-mcp-server.py`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest discover -s tests -v
```

**Commit message:** `Annotate all tools with read-only and destructive hints`

---

### Step 4: Client-visible verification and docs

- [ ] Write the failing test first: extend `tests/test_stdio_smoke.py` to
  assert annotations arrive in `list_tools` over a real stdio round trip
  (spot-check `delete_project` destructive, `list_clients` read-only).
  Expected to FAIL only if serialization drops them; otherwise it passes
  immediately and stands as the regression pin.
- [ ] Implement: readme gains a short "Tool annotations" note; CLAUDE.md's
  new-write-tool rule gains: add the tool to `WRITE_TOOLS`, to
  `DESTRUCTIVE_TOOLS` if applicable, and the structural test enforces the
  annotations.
- [ ] Verify: proofread; no emdashes; suite green.

**Satisfies:** R4

**File(s):** `tests/test_stdio_smoke.py`, `readme.md`, `CLAUDE.md`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest tests.test_stdio_smoke -v
```

**Commit message:** `Verify annotations reach clients; document the annotation rule`

---

## Files Modified (Summary)

| File | Steps |
|------|-------|
| `harvest-mcp-server.py` | 2, 3 |
| `tests/test_annotations.py` | 2 |
| `tests/test_stdio_smoke.py` | 4 |
| `readme.md` | 4 |
| `CLAUDE.md` | 4 |
| this plan file | 1 |

## Notes

- **Upstreamable in full.** Annotations benefit every consumer of the
  upstream server; include them in an upstream PR once proven here (upstream
  would also need the SDK bump, so they travel together).
