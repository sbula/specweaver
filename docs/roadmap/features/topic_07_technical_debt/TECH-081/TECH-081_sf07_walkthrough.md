# Walkthrough: TECH-081 SF-07 — Pure-logic and contract modules do no I/O

Plan: [TECH-081_sf07_implementation_plan.md](TECH-081_sf07_implementation_plan.md).

## CB-1 — the context writer leaves the contract module (FR-19)

### What changed

- `ContextInferrer` moved whole from `workspace/context/inferrer.py` to
  `workspace/analyzers/inferrer.py`. `assurance/graph/topology.py` and
  `workspace/project/interfaces/cli.py` import the new path.
- Tests moved: `test_inferrer.py` to `tests/unit/workspace/analyzers/`; `test_exposes_seam.py` and
  `test_scan_and_infer.py` to `tests/integration/workspace/analyzers/`.
- `tach.toml`: the `inferrer` expose moved from `workspace.context` to `workspace.analyzers`;
  `workspace.project.interfaces` no longer depends on `workspace.context` (unused report). The
  analyzers manifest exposes `inferrer`; the project interfaces manifest drops the edge.
- `B-SENS-03` corpus scope re-pointed. 0 stale mutants.
- `test_logging_rollout.py` imports `inferrer` from its new module. That one edit makes the
  boundary kind `tooling` `[agreed 2026-10-28]`.

### Red first

None of its own: a move proven by the existing tests (plan R5). CB-3's purity guard is the check
that keeps `workspace/context` free of I/O.

### Gate notes

Full suite 11834 passed, 9 skipped; `tests.py cb --kind tooling`, `quality.py cb`, `doc`,
`tach check` green. The `refactor` gate refused the logging test's import split.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) `workspace/analyzers` now writes files. Blue: it is an `adapter` that already reads
  them; the design puts the writer there (AD-12).
- R2 (LOW) `D-SENS-01_design.md:32` names the old path. Blue: a finished story's design records its
  own time; it is not edited.
- R3 (LOW) an empty `tests/integration/workspace/context/` with only `__pycache__` stays on disk.
  Blue: git does not track it; nothing collects from it.
- Cycle 2: no new finding.
