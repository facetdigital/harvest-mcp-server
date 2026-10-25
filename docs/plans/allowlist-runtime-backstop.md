# Plan: Allowlist Runtime Backstop

## Execution Instructions

When executing this plan:

1. **Work step-by-step** - Complete each step fully before moving to the next
2. **Test-first within each step** - Write the failing test before the implementation
3. **Test after each step** - Run the test commands listed
4. **Commit after each step** - Use the provided commit message
5. **Update documentation continuously** - `readme.md`, `CLAUDE.md`, this file,
   `docs/plans/development-roadmap.md`
6. **Mark completion** - Move this item to "Completed" in the roadmap

---

## Summary

`HARVEST_READ_ONLY` is enforced twice: per-tool via `write_refusal` and
centrally in `harvest_request`, which refuses any non-GET call. The
`HARVEST_WRITE_TOOLS` allowlist is enforced only per-tool, because
`harvest_request` cannot see which tool is calling. Consequence: a future
write tool added without its `write_refusal` call is still blocked in
read-only mode but silently bypasses the allowlist. The structural test
catches this at test time; nothing catches it at runtime. This plan closes
that asymmetry by threading the calling tool's name into `harvest_request`
and refusing centrally, fail-closed: a non-GET request with no tool name, or
with a tool name outside the active allowlist, raises before any network
activity.

## Requirements

- **R1:** `harvest_request` refuses any non-GET request whose `tool_name` is
  absent from an active allowlist, raising before any network call.
- **R2:** Fail closed: a non-GET request that supplies NO `tool_name` raises
  whenever an allowlist is active, so an unnamed future writer cannot slip
  through.
- **R3:** The per-tool `write_refusal` path is unchanged: refusal payload
  shapes (`read_only_mode`, `write_not_allowed`) stay byte-identical, and the
  friendly structured refusal still happens before the central raise can.
- **R4:** The structural test is extended: every non-GET `harvest_request`
  call site must pass a `tool_name` matching its enclosing function.
- **R5:** No behavior change when `HARVEST_WRITE_TOOLS` is unset.

## Implementation Steps

### Step 1: Central enforcement in harvest_request

- [ ] Write the failing test first, in `tests/test_write_tools.py`
  (`WriteAllowlistTest` and `HarvestRequestTest`): with the allowlist active,
  `harvest_request("projects/1", {}, method="DELETE",
  tool_name="delete_project")` raises naming the tool and no request is made
  (fake httpx records nothing); the same call with
  `tool_name="delete_time_entry"` (allowlisted) proceeds to the fake client;
  a non-GET call with `tool_name=None` raises while the allowlist is active
  (R2); with the allowlist unset, all of the above behave exactly as today
  (R5); GET calls never require a tool name. Expected to FAIL.
- [ ] Implement: add `tool_name=None` keyword to `harvest_request`. After the
  existing read-only backstop, when `HARVEST_ALLOWED_WRITE_TOOLS is not None`
  and `method != "GET"`: raise if `tool_name is None` or
  `tool_name not in HARVEST_ALLOWED_WRITE_TOOLS`, with a message naming the
  method, path, and tool (or "unnamed caller") and echoing the allowed list.
- [ ] Verify green.

**Satisfies:** R1, R2, R5

**File(s):** `harvest-mcp-server.py`, `tests/test_write_tools.py`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest tests.test_write_tools -v
```

**Commit message:** `Enforce the write allowlist centrally in harvest_request`

---

### Step 2: Thread tool names through all write call sites

- [ ] Write the failing test first: extend `GuardStructureTest` so every
  non-GET `harvest_request` call must pass a `tool_name` keyword whose value
  is a string literal equal to the enclosing function's name; a missing or
  mismatched `tool_name` fails the suite. Expected to FAIL (no call site
  passes it yet).
- [ ] Implement: add `tool_name="<function name>"` to all 19 write call
  sites (the 17 pre-existing write tools plus `update_time_entry` and
  `delete_time_entry`). A scripted transform keyed on the enclosing function
  name is acceptable; review the full diff afterward.
- [ ] Verify green: full suite passes, including the behavior tests from
  Step 1 exercised through real tools (call `delete_project` with the
  allowlist active and `write_refusal` bypassed via monkeypatch, and confirm
  the central layer still refuses).

**Satisfies:** R3, R4

**File(s):** `harvest-mcp-server.py`, `tests/test_write_tools.py`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest discover -s tests -v
```

**Commit message:** `Pass tool names to harvest_request from every write tool`

---

### Step 3: Document the two-layer model

- [ ] Test-first: n/a (documentation).
- [ ] Implement: readme's allowlist section gains one sentence: the allowlist
  is enforced twice, per-tool and centrally in the request helper, matching
  read-only mode. CLAUDE.md's conventions section updates the new-write-tool
  rule: a new write tool must appear in `WRITE_TOOLS`, call
  `write_refusal("<name>")`, and pass `tool_name="<name>"` to
  `harvest_request`; the tests enforce all three.
- [ ] Verify: proofread; no emdashes.

**Satisfies:** R1 through R4 (documentation of)

**File(s):** `readme.md`, `CLAUDE.md`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
grep -c 'tool_name' CLAUDE.md   # >= 1
```

**Commit message:** `Document two-layer allowlist enforcement`

---

## Files Modified (Summary)

| File | Steps |
|------|-------|
| `harvest-mcp-server.py` | 1, 2 |
| `tests/test_write_tools.py` | 1, 2 |
| `readme.md` | 3 |
| `CLAUDE.md` | 3 |
