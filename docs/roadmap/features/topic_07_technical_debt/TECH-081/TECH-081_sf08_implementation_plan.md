# Implementation Plan: The Layer Check Reports Clean While the Layers Are Broken [SF-08: The guard]
- **Feature ID**: TECH-081
- **Sub-Feature**: SF-08 — The guard
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-08
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf08_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-20: `tach check` fails on any import loop (`forbid_circular_dependencies = true`), and no
`deprecated` dependency is left. The two architecture pages point at the enforced rules instead of
stale tables (design §Developer Guides). No command, option or output changes (NFR-1).

## Research Notes

Read 2026-10-29.

- **No loop is left.** `tach.toml` with `forbid_circular_dependencies = true` added: `tach check`
  exit 0, "All modules validated". Probe: the same file plus a cycle edge
  (`workspace.ast.adapters → graph`, while `graph → workspace.ast.adapters` exists) exits 1 with
  "Circular dependency detected for module 'specweaver.graph'". tach checks loops over the declared
  `depends_on`; `exact = true` already fails a declared edge no import uses, so a declared loop is a
  real one.
- **No `deprecated` edge is left** (`grep -c "deprecated = true" tach.toml` → 0, since SF-05 CB-3).
- **`tests/unit/test_tach_sees_every_module.py`** (FR-1, FR-2, FR-3, FR-5): checks `root_module` and
  `ignore_type_checking_imports`; that each `deprecated` edge has a row in the ledger's "Owed by
  TECH-081" table and each row an edge; that each row names a design FR. Since SF-05 it accepts an
  empty table only while the section says "None are left".
- **`test_architecture.py::test_tach_architectural_boundaries`** runs `tach check` and fails on any
  error; it is the scope the FR-15/FR-17 mutants use.
- **The two pages**: `hard_dependency_rules.md` (50 lines) holds per-module consumes/forbids tables in
  the old flat names; `module_dependency_graph.md` (66 lines) a hand-drawn mermaid graph of the same.
  Both already say "Since moved (2026-09-25): … the live rules are in `tach.toml`". Skills link
  both by path (`specweaver-implementation-plan` Phase 1/3, `specweaver-pre-commit` Phase 1/6,
  `specweaver-design` Phase 2), so the files stay; their content changes.
- **`tach show --mermaid -o <file>`** draws the live graph from `tach.toml` (tach 0.34.1).

## Approach (pseudocode, ordered)

**CB-1 — the guard (FR-20)** — kind `tooling` — closes SF-08
1. Red: in `test_tach_sees_every_module.py`, `test_import_loops_fail_the_check` asserts
   `forbid_circular_dependencies is True` (fails: unset), and `test_no_deprecated_edge_is_left` (Q1 `[agreed 2026-10-29]`)
   asserts `_deprecated_edges() == set()` (green today; its proof is a mutant, step 4).
2. Green: `tach.toml` gains `forbid_circular_dependencies = true`. Per Q1 (A), the owed-table test and
   the FR-per-row test go, and the ledger's "Owed by TECH-081" section becomes one closing line.
3. Docs: `hard_dependency_rules.md` — the rules live in `tach.toml` (modules, `depends_on`, interface
   exposes) and each module's `context.yaml` (archetype, consumes, forbids); the three settings
   (`root_module = "forbid"`, `ignore_type_checking_imports = false`,
   `forbid_circular_dependencies = true`) and `exact = true`; which test keeps each true
   (`test_tach_architectural_boundaries`, `test_tach_sees_every_module`, `test_manifests_match_tach`,
   `test_pure_modules_do_no_io`); the old tables go. `module_dependency_graph.md` — the hand-drawn
   graph goes; `tach show --mermaid` draws the live one; the `run_setup` note stays and gains
   `cli_kit` and `run_doors`. Design doc row ✅.
4. Mutants (FR-20 campaign, corpus `TECH-081`): `loops-allowed-again` (the setting removed →
   the new test red); `deprecated-edge-back` (one edge marked `deprecated` → the new test red).

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| arch | `test_import_loops_fail_the_check` | FR-20 (loops fail) | the setting is unset |
| arch | `test_no_deprecated_edge_is_left` | FR-20 (none left) | mutant `deprecated-edge-back`; green today by SF-05 |
| arch | `test_tach_architectural_boundaries` | FR-20 (a declared loop fails `tach check`) | the probe in Research Notes; as a corpus mutant it crashes tach's pytest plugin (`CircularDependency` panic), so the runner cannot judge it |
| all | the suite | NFR-1 | — |

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–4 | suite green; two mutants killed; stage and stop (closes SF-08) |

After it: the closure gate (`check_fr_coverage.py TECH-081`, `tests.py feature TECH-081`), README
counts, the finished message (`specweaver-feature` Phase 4).

## Documentation

Step 3. No user-facing change.

## Architecture Verification (Phase 3)

Config and tests only; no module moves, no new edge. The pages stop restating what tach enforces,
so they cannot go stale again.

## Audit (Phase 2)

❓ **Q1 — after TECH-081, may a `deprecated` edge ever come back?** Today a `deprecated` edge is
allowed when the ledger has a row naming the FR that removes it. NFR-2 says that after SF-01 a
`deprecated` edge "may only be removed, never added"; FR-20 says none is left.
- **A:** forbid it outright. A test fails on any `deprecated` edge; the owed table and its two
  tests go. A future move that needs a staged edge has to change this test, visibly.
- **B:** keep the owed-table rule for future tickets: a `deprecated` edge is allowed while a
  ledger row names the FR that removes it.

The user chose A `[agreed 2026-10-29]`.

## Consistency (Phase 5)

- Coverage: FR-20 both halves (step 1–2, mutants in step 4); NFR-1 (suite); NFR-2 (no edge added;
  after this SF none can be); FR-5 (the ledger's owed section closes with the edges); design doc row
  for the two pages (step 3). FR-3's proof (each owed edge in the ledger) retires with the table: no
  owed edge can exist, which `test_no_deprecated_edge_is_left` holds.
- Red/Blue, 2 cycles:
  - R1 (MEDIUM) removing the owed-table tests drops the `Proves: TECH-081 FR-3` citations. Blue:
    the new test proves FR-3's end state (no edge without an owner, because no edge); its docstring
    keeps `FR-3`, so `check_fr_coverage` still finds it. Checked at the closure gate.
  - R2 (MEDIUM) tach checks loops over declared edges, not imports. Blue: `exact = true` fails an
    unused declared edge, and `root_module = "forbid"` fails an undeclared import, so a real import
    loop must be declared and is then caught (probe recorded above).
  - R3 (LOW) the skills link both pages. Blue: the files stay; only their content changes.
  - R4 (LOW) `tach show --mermaid` writes a file in the tree. Blue: the page names `-o` with a path
    under `.tmp/`; nothing is committed.
  - Cycle 2: no new finding.
- All decisions are resolved and documented inline in the plan.
