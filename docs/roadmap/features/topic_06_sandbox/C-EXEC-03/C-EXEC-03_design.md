# C-EXEC-03 — Domain-Driven Module Consolidation

**Status**: APPROVED. **COMPLETE** — SF-01, SF-02 committed · **Phase**: 3 · **Feature ID**: 3.26a

| | |
|---|---|
| Touches | every Python file in `src` and `tests` (absolute imports), `tach.toml` |
| Not touched | execution logic or behaviour of the application |
| Reference | `context.yaml` layering in `docs/architecture/architecture_reference.md`; Domain-Driven Design (DDD) |

## What it does

Replaces SpecWeaver's flat `src/specweaver` layout with explicit macro-domains, so a package's place says how
it relates to the rest. Constraints: all 3884 tests pass, `tach check` is updated and passes, no
information or implementation is lost.

| Group | Macro-domain | Packages |
|---|---|---|
| 1 | `workflows` | L1-L5 phases: `drafting`, `planning`, `implementation`, `review`, `pipelines` |
| 2 | `assurance` | pure-logic validation: `validation`, `standards`, topological `graph` |
| 3 | `workspace` | physical environment: `project`, `context` |
| 4 | `interfaces` | external triggers: `api`, `cli` |
| 5 | `core` | state, orchestration, executors: `flow`, `config` (not `loom` — see FR-5 below) |
| 6 | `infrastructure` | external network: `llm` |

`tach.toml` enforces imports across implicit namespace packages, so moving root folders breaks every
`import src.specweaver.<app>` until the sweep rewrites it.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Relocate L1-L5 Phases | System | Relocates directories `drafting`, `planning`, `implementation`, and `review` | Target paths reside inside `src/specweaver/workflows/` |
| FR-2 | Relocate Assurance Bounds | System | Relocates pure-logic discovery `validation` and `standards` | Target paths reside inside `src/specweaver/assurance/` |
| FR-3 | Relocate Workspace Bounds | System | Relocates physical project states `project` and `context` | Target paths reside inside `src/specweaver/workspace/` |
| FR-4 | Relocate API Endpoint Bounds | System | Relocates exterior entry-points `cli` and `api` | Target paths reside inside `src/specweaver/interfaces/` |
| FR-5 | Relocate Core Execution Suite | System | Relocates `flow`, `loom`, and `config` | Target paths reside inside `src/specweaver/core/` |
| FR-6 | Relocate Infrastructure Adapters | System | Relocates the `llm` domain | Target paths reside inside `src/specweaver/infrastructure/` |
| FR-7 | Mirror Unit and Integration Tests | System | Restructures `tests/unit/` and `tests/integration/` to identically match the 6 macro-domains over in `src/` | 1:1 structural parity between tests and code |
| FR-8 | Restructure E2E Test Suite | System | Restructures `tests/e2e/` from a flat tree into explicit business capability folders (by feature or story) | `tests/e2e/` map to features, not python files |
| FR-9 | Update Global Python Imports | System | Sweeps `src/` and `tests/` updating absolute Python import paths `specweaver.*` | Files resolve their dependencies inside the new domains |
| FR-10 | Adjust Architecture Topology Engine | System | Sweeps `tach.toml` and internal architecture graphs | Boundaries accurately describe the 6 macro-domains |
| FR-11 | Relocate Design Documents | System | Moves `docs/architecture/*` into `docs/architecture/` and permanently removes the empty `docs/proposals/design` paths | Design documents reside within `architecture` |
| FR-12 | Relocate Roadmap Folder | System | Moves the entire `docs/roadmap/` directory up into `docs/roadmap/` | Project roadmap structures are elevated out of proposals |

## How the FRs are proven (2026-08-17, `INT-US-01-SF02-MIG`)

Each FR says *"directory X now lives at Y"*. A completed move leaves nothing running to observe, but
it leaves a shape, and a shape is falsifiable. `tests/unit/test_macro_domain_layout.py` asserts it.
Each guard was verified by mutating the tree — `workflows/review` moved back to the top level, a new
flat e2e file, a stray test directory, `tach.toml` renamed off a macro-domain. All four fail.

**Exceptions are named paths, never counts.** A count absorbs the next violation silently —
`test_tach_architectural_boundaries` sat at `fail_count <= 95` for three months (fixed the same day).
A named list absorbs nothing: a fourth stray directory fails, a fifth flat e2e file fails.

**The import sweep reads the AST, not the text.** A regex flags `test_runner_architecture.py`, which
writes `from specweaver.llm import Client` into a temp file inside a triple-quoted string to exercise
the forbids checker — fixture data, not an import.

## Where the tree differs from the FRs

**FR-5: the `loom` clause is struck.** `flow` and `config` are in `core/`. **There is no `loom`
package anywhere in `src/`** — the Loom is the top-level `sandbox/` package (hence
`tests/integration/sandbox/test_loom_stack.py`), top-level by design;
`test_sandbox_is_grouped_by_feature_not_by_layer` guards its internal shape.
`test_the_loom_package_is_the_top_level_sandbox` pins this both ways: it also fails if a `core/loom`
appears, which would mean this note needs revisiting, not the tree.

**FR-7: closed (2026-08-17).** Test directories with no `src/` counterpart:

| Directory | What it holds | Disposition |
|---|---|---|
| `tests/integration/constitution/` | imports `workspace.project.constitution` and `.scaffold` — an ordinary test of `workspace.project` | moved to `tests/integration/workspace/project/` |
| `tests/integration/engine/` | imports `core.flow.handlers.{arbiter,decompose,run_context}` — handler injection pathways | moved to `tests/integration/core/flow/handlers/` |
| `tests/unit/alembic/` | loads a migration module **by path** from repo-root `alembic/versions/`; imports nothing from `specweaver` | kept — mirrors a repo-root directory |
| `scripts` (both tiers) | the dev gates in repo-root `scripts/` | kept — mirrors a repo-root directory |
| `tests/unit/graph_store/` | an empty `__init__.py` left when `graph/core/store` moved | deleted |

The bar for an exception: **the directory mirrors something real** — `alembic/` and `scripts/` exist
at the repo root and are not product code. The `alembic` test also cannot move: it computes
`Path(__file__).parent.parent.parent.parent / "alembic" / "versions" / ...`, so its position is
load-bearing.

**FR-8: closed (2026-08-17).** `tests/e2e/` holds `capabilities/` and `scripts/` only. Sixteen
loose or layer-shaped files moved into capability folders; `interfaces` and `sandbox` were added,
each mirroring a `src/` macro-domain:

| From | To | Why |
|---|---|---|
| `test_cli_bootstrap_e2e.py`, `core/config/test_config_db_across_processes_e2e.py`, `core/flow/test_pipeline_hydration.py`, `core/flow/test_resume_after_failure_journey_e2e.py`, `capabilities/test_cli_lineage_e2e.py` | `capabilities/core/` | config, pipeline hydration and resume, lineage |
| `interfaces/test_cli_colour_e2e.py`, `interfaces/test_implement_usage_journey_e2e.py`, `test_cli_decentralized_e2e.py` | `capabilities/interfaces/` | journeys through the CLI surface |
| `sandbox/test_executor_e2e.py`, the three worktree-isolation journeys, `flow/test_cpp_flow.py` | `capabilities/sandbox/` | executor, worktree isolation, polyglot code-structure atom (`test_cpp_flow.py` drives a `read_symbol` intent, not a pipeline) |
| `test_logging_e2e.py`, `capabilities/test_provider_cli_e2e.py` | `capabilities/infrastructure/` | logging; multi-provider is the LLM adapter |
| `test_polyglot_validation_e2e.py` | `capabilities/assurance/` | validation |

- **`tests/e2e/scripts/` stays**: it drives the repo's dev tooling (mutation corpus CLI, nightly
  timer), not a product capability — recorded as `E2E_NON_CAPABILITY_DIRS`, the same reason
  `scripts` is excused from the src mirror.
- The guard is unconditional: `E2E_FLAT_REMAINDER_FILES` is empty, so a loose file at the tier root
  fails. Every capability folder must mirror a `src/` macro-domain. 216 e2e tests pass, unchanged in
  number.
- **A move can need a code change** — a restructure is not just `git mv`. `test_cli_colour_e2e.py` used
  `Path(__file__).resolve().parents[3]` as the subprocess `cwd`; one level deeper it resolved to
  `tests/e2e/`. It now walks up to the directory holding `pyproject.toml`. A hard-coded ancestor
  index is a hidden dependency on a file's position in the tree.

**FR-9: true as written** — no import in `src/` or `tests/` names a pre-restructure path.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Regression Integrity | 3,884 total test cases MUST pass under execution. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-2 | Architectural Viability | `tach check` MUST yield 0 architectural domain drift validations. **[proof: arch — tach/lint gate, not pytest]** |
| NFR-3 | File Integrity | 0 Loss of files, configs, logic, or models during physical move (Data Retention 100%). |

External dependency: Tach (latest; `tach.toml` check) — its structural constraints are updated by
hand to match the new absolute Python domains.

## Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Retain UUID mapping within Tests | Prevents test regressions | No |

Developer guide owed: **Architecture Bounds** — update the Module Map in the Architecture Reference
(⬜ to be written during Pre-commit).

## Sub-features

| SF | Name | FRs | Depends on | Plan |
|----|------|-----|-----------|------|
| SF-01 | Domain & Documentation Realignment | FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-11, FR-12 | — | [sf01](C-EXEC-03_sf01_implementation_plan.md) |
| SF-02 | Boundary Enforcement (Tach Matrix) | FR-10 | SF-01 | [sf02](C-EXEC-03_sf02_implementation_plan.md) |

- **SF-01**: move `src/specweaver/*` (flat mapping) into the macro-domains, restructure `tests/`,
  patch absolute imports, move docs. Output: 4 new macro-domains with remapped imports. Runs first —
  moves and strings, repairing IDE errors.
- **SF-02**: repair the architectural test boundaries (Graph & Tach) for the new namespaces. Output:
  valid `tach.toml`, clean `tach check`, 3884 passing tests. Then locks boundary validation.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Domain File Realignment | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Boundary Matrix Sync | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
