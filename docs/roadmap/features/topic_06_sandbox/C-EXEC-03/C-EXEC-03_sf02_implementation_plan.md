# C-EXEC-03 SF-02 — Boundary Matrix Sync

**Status**: APPROVED · **Feature ID**: 3.26a (SF-02) · **Depends on**: SF-01 ·
Design: [C-EXEC-03_design.md](C-EXEC-03_design.md) §Sub-features → SF-02

**FRs owned: FR-7, FR-8, FR-11, FR-12.** The test-tier mirror, the e2e capability tree, and the
documentation moves. Recorded 2026-08-17 under `specweaver-dev` §3.2c, from
`INT-US-01-SF02-MIG`.

**FR-8 is closed (2026-08-17).** Sixteen files moved into capability folders, `interfaces` and
`sandbox` added to `tests/e2e/capabilities/`, and the guard is now unconditional — a loose e2e file at
the tier root fails rather than joining an exception list. `tests/e2e/scripts/` remains as a permanent
non-capability directory, for the same reason `scripts` is excused from the src mirror: it drives dev
tooling, not a product capability. 216 e2e tests pass, unchanged in number.

**FR-7 is closed (2026-08-17).** Of the four directories with no `src/` counterpart, two held ordinary
tests of `workspace.project` and `core.flow.handlers` under invented top-level names and were moved to
their mirrors; two — `scripts` and `alembic` — mirror repo-root directories that genuinely exist and are
not product code. The guard keeps them as named exceptions, so a third fails.

## Goal

After SF-01's moves, make `tach.toml` and the internal architecture evaluation define and enforce
the 6 macro-domains (`workflows`, `assurance`, `workspace`, `interfaces`, `core`, `infrastructure`).

## Changes

1. **`tach.toml`**:
   - rewrite `[[modules]]` blocks for the nested domains, and `[[interfaces]]` expose blocks via the
     macro-domain paths;
   - deep paths, e.g. `path = "src.specweaver.interfaces.cli"`, `path = "src.specweaver.workflows.planning"`;
   - `depends_on` arrays match the new locations (e.g. `src.specweaver.core.flow` consumes
     `src.specweaver.workflows.drafting`);
   - edit autonomously; enforce with `tach check`.
2. **Graph evaluator** — `src/specweaver/assurance/graph/` (formerly `src/specweaver/graph/`) runs
   its topological evaluations under the new tree; its unit tests pass.

## Tests

- `tach check` from the command line — MUST yield exactly 0 architectural errors or dependency
  violations.
- `tach sync` repairs minor drift if `context.yaml` and `tach.toml` disagree.

## Decisions (audit)

1. **Tach boundary level — Option A (Deep Mapping)**: `tach.toml` tracks the deep component tier
   (e.g. `path = "src.specweaver.workflows.planning"`), keeping boundaries between components
   *within* a macro-domain.
