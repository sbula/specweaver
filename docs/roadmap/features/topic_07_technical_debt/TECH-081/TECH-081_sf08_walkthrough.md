# Walkthrough: TECH-081 SF-08 — The guard

Plan: [TECH-081_sf08_implementation_plan.md](TECH-081_sf08_implementation_plan.md).

## CB-1 — the guard (FR-20) — closes SF-08

### What changed

- `tach.toml`: `forbid_circular_dependencies = true`. No loop was left; `tach check` stays green.
- `test_tach_sees_every_module.py`: `test_import_loops_fail_the_check` and
  `test_no_deprecated_edge_is_left` replace the owed-table tests (Q1 `[agreed 2026-10-29]`: no
  `deprecated` edge may come back). The ledger's "Owed by TECH-081" section is a closing note.
- `hard_dependency_rules.md` and `module_dependency_graph.md` no longer copy the rules: they say
  where the rules live (`tach.toml`, each `context.yaml`), the four strict settings, which test keeps
  each true, and how to draw the live graph (`tach show --mermaid`).
- Closure: `check_fr_coverage.py TECH-081` found FR-10, FR-11, FR-14 and FR-16 cited by no test,
  though `tach check` enforces them. `test_architecture.py` now cites them; FR-14 gained its first
  mutant (`flow-uses-a-private-detector`).
- Mutants that earlier TECH-081 commits left without an anchor were re-anchored and re-run
  (all OBJECTED): `TECH-068` `the-approved-crossing-is-undeclared-again` and `TECH-081`
  `unknown-archetype` (manifest edits in SF-02/SF-03); `D-INTL-08` `contract-detects-again` and
  `C-EXEC-06` `reconcile-failure-stored-completed`, whose anchors matched twice. The three FR-3
  mutants on the owed table became one, `unowned-edge-back`.
- README counts: 11,905 tests, 50 corpora, 1,221 mutants.

### Red first

`test_import_loops_fail_the_check` failed: the setting was unset. `test_no_deprecated_edge_is_left`
was green from SF-05 on; mutant `deprecated-edge-back` shows it can fail.

### Proof

FR-20: `loops-allowed-again`, `deprecated-edge-back`; FR-3: `unowned-edge-back`; FR-14:
`flow-uses-a-private-detector` — all OBJECTED. A declared loop (`workspace.ast.adapters → graph`)
fails `tach check` (probe in the plan); as a corpus mutant it crashes tach's pytest plugin, so the
runner cannot judge it and it is not in the corpus. 0 stale.

Works for real: `tach check` prints "All modules validated" with no `deprecated` line; `sw --help`
(run with a temporary home) lists all 25 commands.

### Gate notes

Full suite 11834 passed, 9 skipped; `tests.py cb --kind tooling`, `tests.py feature TECH-081
--kind tooling`, `check_fr_coverage.py TECH-081` (20 of 20), `quality.py cb`, `doc`,
`check_proof_tier.py`, `tach check` green. A corpus mutant with an empty `new` broke corpus loading;
fixed to `forbid_circular_dependencies = false`.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) citing four FRs from `test_architecture.py` could be a citation without a proof.
  Blue: each has a mutant in that file's scope that the suite kills.
- R2 (MEDIUM) a future move that needs a staged edge must now edit a test. Blue: the user's Q1
  choice; the edit is visible in review.
- R3 (LOW) the pages no longer show a picture. Blue: the command draws the live one; a drawn copy
  went stale twice.
- Cycle 2: no new finding.
