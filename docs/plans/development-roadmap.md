# Development Plan

Fork-internal document. Like CLAUDE.md, this file and the whole `docs/plans/`
directory are excluded when building upstream PR branches (cherry-pick code
commits only).

## Next Immediate Step

### Live validation of the new time-entry write tools

**Goal:** Exercise `update_time_entry`, `delete_time_entry`, and the
`HARVEST_WRITE_TOOLS` allowlist against the real Harvest API through their
first production consumer, running from this branch. Confirm both refusal
shapes (`read_only_mode`, `write_not_allowed`) empirically in a live MCP
session, not just in the unit suite. Any findings that need server changes
come back to this branch as fixes.

**Status:** Ready to execute. Driven by the consuming workflow, so no plan
file lives here; this repo's part is reacting to what validation surfaces.

---

## Upcoming

### Upstream submission and sync

**Goal:** Submit the feature work upstream and converge back to main. The
mechanics live in CLAUDE.md's "Next steps": cherry-pick the code commits onto
a branch cut from `upstream/main` (excluding fork-internal docs), submit the
PR, check periodically for the merge, then sync main and retire the feature
branch and draft PR #2.

### GitFlow-like branching strategy for fork maintenance

**Goal:** Define a durable branching model that lets this fork continuously
pull from upstream, submit clean PRs upstream, and keep fork-private changes
(operating docs, configs, possibly private tools) in source control without
ever leaking them into upstream submissions. Should replace today's ad hoc
"run from a feature branch and remember what to exclude" arrangement.
Sequenced after live validation of the new tools. [Needs Planning]

### Allowlist runtime backstop

**Goal:** Thread the calling tool's name through `harvest_request` so
`HARVEST_WRITE_TOOLS` gains a central enforcement layer symmetric with
read-only mode. Today the allowlist is enforced per-tool plus a structural
test; read-only is enforced per-tool plus centrally. A deliberate, recorded
asymmetry worth closing. [Needs Planning]

### Dependency hygiene pass

**Goal:** Cap the open version floors (`mcp<2`; consider `httpx` too),
refresh `uv.lock` to clear stale pins (h11 past its CVE fix, newer mcp 1.x),
pin the Dockerfile base images by digest, and add a `.dockerignore`. One
deliberate commit, kept off the critical path of feature work because it is
the one change that can break the server rather than extend it.
[Needs Planning]

### MCP tool annotations

**Goal:** Add `readOnlyHint` / `destructiveHint` annotations to all 36 tools
so MCP clients can distinguish destructive tools programmatically. Depends on
the dependency hygiene pass (requires an mcp SDK newer than the pinned
1.4.1). [Needs Planning]

### Extend test coverage to pre-existing tools

**Goal:** Pin request-building behavior of the read tools and the
pre-existing write tools, so upstream merges can be verified mechanically
instead of by re-reading the diff. The guard-coverage and passthrough tests
are the seed; this grows them toward full-surface coverage. [Needs Planning]

---

## Completed

### Time-entry write tools, allowlist, centralized read-only enforcement (2026-08-06)

`update_time_entry`, `delete_time_entry`, `HARVEST_WRITE_TOOLS` fail-closed
allowlist, centralized read-only refusal in `harvest_request`, 204 handling,
and a 20-test suite with a structural guard-coverage check. Lives on
`feature/time-entry-write-tools`, parked in draft PR #2.
