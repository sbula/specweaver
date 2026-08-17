# Implementation Plan: Boundary Matrix Sync (SF-02)

**FRs owned: FR-7, FR-8, FR-11, FR-12.** The test-tier mirror, the e2e capability tree, and the
documentation moves. Recorded 2026-08-17 under `specweaver-dev` §3.2c, from
`INT-US-01-SF02-MIG`.

**FR-8 is closed (2026-08-17).** Sixteen files moved into capability folders, `interfaces` and
`sandbox` added to `tests/e2e/capabilities/`, and the guard is now unconditional — a loose e2e file at
the tier root fails rather than joining an exception list. `tests/e2e/scripts/` remains as a permanent
non-capability directory, for the same reason `scripts` is excused from the src mirror: it drives dev
tooling, not a product capability. 216 e2e tests pass, unchanged in number.

**FR-7 is still not fully met**, and its guard uses named exceptions rather than a count: four test
directories have no `src/` counterpart. The gap cannot grow by one, and it is not closed.


- **Feature ID**: 3.26a (SF-02)
- **Status**: APPROVED
- **Design Doc**: `docs/roadmap/phase_3/feature_3.26a/feature_3.26a_design.md`

## Overview
Repairs the broken architectural boundaries after the SF-01 physical directory migrations. Executes
targeted sweeps across the `tach.toml` configuration matrix and internal architecture topological
evaluation nodes to strictly define and enforce the mappings of the 6 newly generated Domain-Driven
macro boundaries (`workflows`, `assurance`, `workspace`, `interfaces`, `core`, `infrastructure`).
This will lock the architecture in place.

## Resolved Technical Audits
> [!NOTE]
> **Resolution 1 (Tach Modularity Boundary Level):** We will implement **Option A (Deep Mapping)**.
> We will strictly update `tach.toml` to track boundaries at the deep component tier (e.g.,
> `path = "src.specweaver.workflows.planning"`) in order to preserve absolute boundary protection
> between internal components *within* the macro-domains.

## Proposed Changes

### Component: Topological `tach.toml` Enforcer Updates
- Overhaul `tach.toml` to repair the global dependency tree. 
- Rewrite `[[modules]]` blocks to map cleanly to the deeply nested domains. 
- Rewrite `[[interfaces]]` expose blocks to route cleanly via the macro-domain paths. 

#### [MODIFY] tach.toml
- `path = "src.specweaver.interfaces.cli"` -> `path = "src.specweaver.interfaces.cli"`
- `path = "src.specweaver.workflows.planning"` -> `path = "src.specweaver.workflows.planning"`
- Ascertain that internal `depends_on` arrays precisely match the re-mapped deep string locations (e.g. `src.specweaver.core.flow` consumes `src.specweaver.workflows.drafting`).
- Enforce strict boundary isolation natively via `tach check`.
- *Note for Agent*: Execute changes autonomously in `tach.toml`.

### Component: Internal Graph Evaluator Sync
- Ensure `src/specweaver/assurance/graph/` (formerly `src/specweaver/graph/`) internal topological
  evaluations operate normally without crashing under the new 6-domain tree. Validate this by
  verifying that the unit tests for the graph pass successfully. 

## Verification Plan

### Automated Tests
- Run `tach check` manually at the command line. This acts as our primary deterministic compiler. 
- It MUST yield exactly 0 Architectural errors or dependency violations.

### Manual Verification
- Execute `tach sync` to auto-repair minor drift gaps natively if `context.yaml` drifts mismatch.
