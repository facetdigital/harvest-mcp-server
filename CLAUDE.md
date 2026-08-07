# harvest-mcp-server (facetdigital fork)

This is Facet Digital's fork of taiste/harvest-mcp-server. Upstream remote is
`taiste`, origin is the fork.

## Current operating state (2026-08-07)

**This repo deliberately runs from the branch `feature/time-entry-write-tools`
as if it were main.** Do not switch the checkout back to main or tidy the
branch state; the live Harvest MCP server on this machine launches from this
working copy. The branch adds `update_time_entry`, `delete_time_entry`, the
`HARVEST_WRITE_TOOLS` fail-closed allowlist, centralized read-only
enforcement in `harvest_request`, and the test suite under `tests/`.

The branch is pushed to origin and parked in **draft PR #2**, assigned to
Scott, intentionally unmerged.

## Next steps (in order, Scott decides timing)

1. **Submit an equivalent PR upstream** to taiste/harvest-mcp-server. Build
   the upstream branch from the code commits only: this CLAUDE.md commit is
   fork-internal and must be excluded (cherry-pick the code commits onto a
   fresh branch cut from upstream/main). Keep the PR description generic.
2. **Check periodically whether upstream merged it.** Historical review
   latency on that repo ranges from next-day to 2.5 months.
3. **When upstream merges:** switch this checkout back to main, sync main
   with upstream, confirm the merged result matches this branch (run
   `uv run python -m unittest discover -s tests`), then close draft PR #2
   and delete the feature branch locally and on origin.
4. **If upstream stalls or declines:** decide whether to merge PR #2 into
   the fork's main instead and carry the divergence.

## Conventions

- Run tests with `uv run python -m unittest discover -s tests -v` (stdlib
  unittest only; do not add test dependencies casually, since pyproject.toml
  and uv.lock are deliberately untouched by the feature branch).
- Any new write tool must be added to `WRITE_TOOLS` and must call
  `write_refusal("<its name>")` before building its request; the test suite
  enforces both structurally.
- When pulling from upstream, re-run the test suite before trusting the
  merged result; the guard-coverage test is the check that upstream additions
  did not bypass write gating.
- Never use emdashes in produced content.
