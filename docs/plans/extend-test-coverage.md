# Plan: Extend Test Coverage to Pre-existing Tools

## Execution Instructions

When executing this plan:

1. **Work step-by-step** - Complete each step fully before moving to the next
2. **Test-first within each step** - This plan IS tests; each step's "failing
   first" discipline means writing assertions against current behavior and
   confirming they pass against it, then standing as regression pins. A pin
   that fails on write reveals a wrong assumption: investigate before
   adjusting the assertion.
3. **Test after each step** - Run the test commands listed
4. **Commit after each step** - Use the provided commit message
5. **Update documentation continuously** - `CLAUDE.md`, this file,
   `docs/plans/development-roadmap.md`
6. **Mark completion** - Move this item to "Completed" in the roadmap
7. **Scope discipline:** this plan pins EXISTING behavior, including known
   warts. It changes no production code. Behavior fixes discovered along the
   way become roadmap items, not drive-by edits.

---

## Summary

The current suite covers write gating, the two new time-entry tools, and one
passthrough pin. The other 32 tools' request construction is unverified, so
an upstream merge that subtly changes a query parameter or request body can
only be caught by re-reading the diff. This plan grows the suite until every
tool's request shape is pinned, prioritized by risk: write-tool request
bodies first, then the shaped read tools, then table-driven query-parameter
pins for the plain readers, finished by a completeness check that keeps
future tools from shipping untested.

## Requirements

- **R1:** Every pre-existing write tool has a request-body pin: correct
  path, method, field-by-field body construction, and omission behavior
  (absent optional args produce absent keys, never nulls).
- **R2:** The shaped read tools' transformations are pinned as they are
  today: `list_estimates` strips `line_items` unless `include_line_items`;
  `get_unsubmitted_timesheets` filters on `is_closed` and fabricates its
  pagination fields (pin the fabrication, with a comment naming it a known
  wart); `get_estimate_by_number` paginates until falsy `next_page` and
  raises on not-found.
- **R3:** Every plain read tool has a query-parameter pin, table-driven so
  each new case is one row.
- **R4:** A completeness test fails when any registered tool has no
  corresponding test coverage marker, so future tools cannot ship untested.
- **R5:** No production code changes.

## Implementation Steps

### Step 1: Write-tool request-body pins

- [ ] Write the pins: `tests/test_request_shapes.py`, stub-based like
  `TimeEntryRoutingTest`. For each of the 15 pre-existing write tools
  (project, task-assignment, user-assignment, estimate CRUD, timers,
  `create_time_entry`, `change_estimate_state`, `send_estimate_message`):
  a full-args case (every field lands, correct path and method) and a
  minimal-args case (only required fields present in the body). Include the
  documented quirks as explicit assertions: `notes` int coercion in the
  time-entry tools, `line_items` and `recipients` passed through untouched.
- [ ] Verify green against current behavior.

**Satisfies:** R1

**File(s):** `tests/test_request_shapes.py`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest tests.test_request_shapes -v
```

**Commit message:** `Pin request bodies for all pre-existing write tools`

---

### Step 2: Shaped-read-tool pins

- [ ] Write the pins, same file or `tests/test_response_shaping.py`:
  `list_estimates` with and without `include_line_items` (stripping is
  per-estimate, other fields untouched, default per_page override to 25);
  `get_unsubmitted_timesheets` (open entries kept, closed dropped, fabricated
  `total_pages`/`total_entries` pinned as-is with a wart comment);
  `get_estimate_by_number` (finds on page two via `next_page`, raises with
  the number in the message when absent, per_page 2000 requested).
- [ ] Verify green against current behavior.

**Satisfies:** R2

**File(s):** `tests/test_response_shaping.py`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest tests.test_response_shaping -v
```

**Commit message:** `Pin the shaped read tools' transformations`

---

### Step 3: Table-driven query-parameter pins for plain readers

- [ ] Write the pins: one table mapping each plain read tool to (args in,
  expected params out, expected path), covering: boolean-to-string
  conversions ("true"/"false"), int-to-string conversions, defaulted values
  (`list_users` forcing `is_active` and `per_page`, `list_estimates`
  per_page 25), date passthroughs, and the project-scoped vs account-wide
  path switch in `list_task_assignments` / `list_user_assignments`. One
  subTest per row.
- [ ] Verify green against current behavior.

**Satisfies:** R3

**File(s):** `tests/test_request_shapes.py` (reader table)

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest tests.test_request_shapes -v
```

**Commit message:** `Pin query parameters for all plain read tools`

---

### Step 4: Coverage completeness check

- [ ] Write the failing test first: a structural test that enumerates every
  `@mcp.tool()` function via AST and asserts each name appears in a
  COVERED_TOOLS registry maintained in the test package (each pin file
  registers the tools it covers). Expected to FAIL until the registry lists
  all tools, which forces an honest accounting of Steps 1 through 3.
- [ ] Implement: the registry, populated by the existing and new test
  modules.
- [ ] Verify green: full suite; deliberately comment out one registration
  and confirm the completeness test fails, then restore it.

**Satisfies:** R4

**File(s):** `tests/test_coverage_completeness.py`, small registrations in
the other test modules

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest discover -s tests -v
```

**Commit message:** `Fail the suite when any tool lacks request-shape coverage`

---

### Step 5: Document the testing bar

- [ ] Test-first: n/a (documentation).
- [ ] Implement: CLAUDE.md's conventions gain the rule: every tool ships with
  request-shape pins and a coverage registration; upstream merges are
  verified by running the suite, and a pin failing after a merge means
  upstream changed request behavior and the change gets read before the pin
  is updated.
- [ ] Verify: proofread; no emdashes.

**Satisfies:** R4 (documentation of), supports the CLAUDE.md upstream-pull
convention

**File(s):** `CLAUDE.md`

**Test:**
```bash
cd ~/src/facetdigital/harvest-mcp-server
uv run python -m unittest discover -s tests
```

**Commit message:** `Document the request-shape coverage bar`

---

## Files Modified (Summary)

| File | Steps |
|------|-------|
| `tests/test_request_shapes.py` | 1, 3 |
| `tests/test_response_shaping.py` | 2 |
| `tests/test_coverage_completeness.py` | 4 |
| `CLAUDE.md` | 5 |

## Notes

- **This plan makes upstream pulls mechanical.** After it lands, the
  CLAUDE.md rule "re-run the suite before trusting a merge" covers request
  construction for every tool, not just write gating.
- **Fully upstreamable**, and worth including in a second upstream PR once
  proven: upstream gains a regression net for its whole surface.
- **Known warts are pinned, not fixed** (the `get_unsubmitted_timesheets`
  pagination fabrication chief among them). Fixing them is future roadmap
  work that would then deliberately update the pins.
