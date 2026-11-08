# Implementation Plan: Two Graph Engines in Two Homes [SF-02: One home]
- **Feature ID**: TECH-088
- **Sub-Feature**: SF-02 — One home
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-088/TECH-088_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-088/TECH-088_sf02_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-08)

## Scope

FR-5 and FR-6. After SF-02, the module graph lives in `graph/topology/`, a tach module of its own;
`assurance/graph/` holds only the boundary rule `[agreed 2026-11-08]`. No behaviour changes: every
caller answers as before (FR-6), proven by the tests that already cover them, moved with the code.

## What moves (measured 2026-11-08)

| From `assurance/graph/` | To `graph/topology/` | Imported by (src) |
|---|---|---|
| `topology.py` | `topology.py` | `core/flow/handlers/changed_code.py`, `validation.py`, `sandbox/language/core/boundary_check.py`, `workspace/project/interfaces/cli.py`, `workspace/project/tach_sync.py`, `assurance/graph/boundary_rule.py` |
| `loader.py` | `loader.py` | `graph/interfaces/cli.py`, `interfaces/run_setup/builder.py` |
| `selectors.py` | `selectors.py` | `loader.py` |
| `hasher.py` | `hasher.py` | `core/flow/interfaces/cli.py`, `changes.py`, `topology.py` |
| `changes.py` | `changed_files.py` | `core/flow/handlers/changed_code.py` |
| stays: `boundary_rule.py` | — | `sandbox/language/core/boundary_check.py` |

References: 13 source files, 32 test files, 8 `context.yaml` files, 1 baseline
(`scripts/baselines/class_health.json`), 2 mutants (`TECH-004_mutants.json`, `loader.py`), and 5
living docs. Test files that mirror the moved code: `tests/unit/assurance/graph/` (all but
`test_boundary_rule.py`, with its whole `conftest.py`: `test_boundary_rule.py` uses none of its 11
fixtures, measured 2026-11-08) and
`tests/integration/assurance/graph/test_hasher_integration.py`; they move to
`tests/{unit,integration}/graph/topology/`.

## Commit boundaries

### CB-1 (closes SF-02, HITL): the move — FR-5, FR-6

**Tests first:**
- `tests/unit/test_the_module_graph_has_one_home.py` (FR-5):
  - `src/specweaver/assurance/graph/` holds `boundary_rule.py`, `__init__.py` and `context.yaml`,
    nothing else;
  - no file under `src/` or `tests/` imports or patches `specweaver.assurance.graph.topology`,
    `.loader`, `.selectors`, `.hasher` or `.changes` (an AST walk for imports, a text search for
    `patch("…")` strings);
  - `tach.toml` has `specweaver.graph.topology` with `depends_on` `workspace.analyzers` and
    `workspace.context`; `specweaver.graph` keeps `[infrastructure.database, workspace.ast.adapters]`.
  Red today: the files are in `assurance/graph/`, and no `specweaver.graph.topology` module exists.
  Mutant: a re-export `assurance/graph/topology.py` put back → the guard fails.
- FR-6 is proven by the tests that already cover each caller, moved with the code and unchanged
  in what they assert: `test_boundary_rule_from_manifests.py`, `test_boundary_rule_holds.py`
  (sandbox check), `test_init_writes_boundaries_e2e.py` and `test_topology_e2e.py` (`sw scan`),
  `test_cli_graph.py`, `test_topology_wiring.py` (`sw graph build`), `test_build_run.py`,
  `test_run_carries_the_module_graph.py` (run setup), `test_tests_run_for_what_changed.py`
  (changed files). Each gains a `Proves: TECH-088 FR-6` line.

**Then the code:**
0. Before the script: `pytest --collect-only -q` → `.tmp/collected_before.txt`.
1. A one-off script (in `.tmp/`, its count in the walkthrough, as in `TECH-090` SF-04 CB-1) uses
   `git mv` for the five files and the mirrored tests, then rewrites every dotted and slash form of
   the old paths in `src/`, `tests/`, `scripts/`, the 8 `context.yaml` files and the living docs.
   No re-export stays behind.
2. `tach.toml`: the new module `specweaver.graph.topology`; `topology.engine` leaves
   `specweaver.graph`'s interface; the new module exposes what `assurance.graph` exposed for these
   files (`TopologyGraph`, `ContextSelector`, `topology.load_nodes`) plus the engine and the loader
   functions its callers use. Callers depend on `specweaver.graph.topology`; those that also use the
   boundary rule (`sandbox`) keep `assurance.graph`. `assurance.graph` depends on
   `specweaver.graph.topology` only.
3. `graph/topology/context.yaml` (new): `archetype: pure-logic` (AD-3), the `consumes` and `forbids`
   `assurance/graph` had for these files. `assurance/graph/context.yaml`: its purpose is the boundary
   rule alone, and it consumes `specweaver/graph/topology`.
4. `known_boundary_violations.md`: the two `File I/O inside pure-logic` rows name the new paths.
5. `class_health.json`: the `TopologyGraph` key renamed to the new path; `TECH-004`'s two loader
   mutants point to the new file and are re-pinned; `stale_mutants.py` shows 0.
6. Before any other edit to `tests/`: `.tmp/check_test_rewrite.py` passes, and
   `pytest --collect-only -q` → `.tmp/collected_after.txt` has the same count and the same node ids
   with the moved paths mapped. Only then are the `Proves: TECH-088 FR-6` lines added.

## Research Notes

- **`exact = true` in `tach.toml`:** tach fails on a declared edge nothing uses. Nothing in the
  moved code imports `specweaver.graph` core yet, so the design's FR-5 edge `specweaver.graph`
  arrives in SF-03, with the depth constant that needs it.
- `ignore_type_checking_imports = false`: `hasher.py:20`'s `TYPE_CHECKING` import of
  `workspace.context` counts, so `workspace.context` is a real edge.
- Simulated 2026-11-08 (design): no cycle; `graph.topology` reaches only `analyzers`, `ast.parsers`
  and `context`.
- `graph/core` and `graph/lineage` import nothing from `graph/topology` (grep 2026-11-08), so
  `specweaver.graph` keeps its two edges.
- Living docs that name the old path: `docs/dev_guides/pluggable_contexts.md`,
  `docs/architecture/03_system_topology/module_dependency_graph.md`,
  `docs/architecture/02_bounded_contexts/domain_llm_and_telemetry.md`,
  `docs/architecture/06_lessons_and_future/known_boundary_violations.md`. The dated analyses and the
  closed feature documents are history and are not edited.

## Architecture (Phase 3)

| Change | Module | Rule | Verdict |
|---|---|---|---|
| five files | `graph.topology` (new) | `pure-logic` with the two recorded file-read rows (AD-3); no LLM, no sandbox | ok |
| boundary rule | `assurance.graph` | consumes `graph.topology` (downward) | ok |
| callers | `core.flow.*`, `sandbox`, `workspace.project`, `interfaces.run_setup`, `graph.interfaces` | each edge to `graph.topology` replaces one to `assurance.graph`; `sandbox` keeps both | ok |

No cycle: `graph.topology` reaches none of its callers.

## Decisions (Phase 4)

All seven proposals taken by the user `[agreed 2026-11-08]`:

- **B1** `graph.topology` → `specweaver.graph` arrives in SF-03 with the depth constant; tach's
  `exact = true` refuses it earlier. FR-5 in the design says so.
- **B2** One boundary, closing SF-02.
- **B3** `changes.py` becomes `changed_files.py` in this move. FR-11's rename of it moved from SF-04
  to SF-02, and the design records the move.
- **B4** The living docs, manifests and ledger are updated; dated analyses and closed feature
  documents are not.
- **B5** The mirrored tests move to `tests/{unit,integration}/graph/topology/`.
- **B6** No re-export stays in `assurance/graph/`.
- **B7** The `class_health.json` key is renamed; `TECH-004`'s two loader mutants are re-pinned.
- **The test rewrite is checked** (the user, at Phase 4): the script rewrites the same tests that
  prove FR-6, so `.tmp/check_test_rewrite.py` reads `git diff -M` over `tests/` and passes only when
  every removed line, with the old paths replaced by the new ones, equals an added line — no
  assertion changed, no line deleted — and every file is a rename or one of those edits. The suite
  is collected before and after: the count of collected tests is equal, and the node ids are equal
  once the moved paths are mapped. Both results go in the walkthrough `[agreed 2026-11-08]`.

## Consistency and red/blue (Phase 5), 2 cycles

- FR-5 has a guard that is red today and a mutant (a re-export put back). FR-6 is proven by the
  existing caller tests, and the test-rewrite check proves the move changed none of them. NFR-1
  holds by that same check; NFR-2 by `tach check` and the guard's `depends_on` assertions.
- Fixed: the plan split `tests/unit/assurance/graph/conftest.py`; a split would add lines the
  rewrite check cannot map and would copy fixtures into a duplication clone. The boundary-rule
  tests use none of its fixtures, so the whole file moves.
- Fixed: the design's FR-5 named a `specweaver.graph` edge that tach refuses until SF-03 (B1); the
  design now says when it arrives.
- Fixed: SF-04's scope listed three renames; it now lists the other two, and its guard still covers
  all three (B3).
- Closed (the user, at approval): the guard's text search finds a `patch("…")` path only when it is
  written in full, but a path built from pieces cannot escape either. With no re-export, any old
  path raises `ModuleNotFoundError` when the test runs, so the full suite catches it
  `[agreed 2026-11-08]`.
