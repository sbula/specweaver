# Design: Domain-Driven Module Consolidation

- **Feature ID**: 3.26a
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3.26a/feature_3.26a_design.md

## Feature Overview

Feature 3.26a adds Domain-Driven Module Consolidation to the core SpecWeaver architecture. It solves
the problem of flat, decoupled directories by restructuring root modules into explicit macro-domains
(`workflows`, `assurance`, `workspace`, `interfaces`). It interacts meticulously with every single
Python file across `src` and `tests` to update absolute import paths, and `tach.toml` to enforce
boundaries, and does NOT touch the internal execution logic or behavior of the application itself.
Key constraints: All 3884 tests must pass, `tach check` must be updated and pass successfully, and
no information or functional implementation can be lost.

## Research Findings

### Codebase Patterns
- Currently, `src/specweaver` structure possesses a flat layout. The mapping corresponds exclusively to specific logical boundaries but doesn't denote their systemic relation.
- **Group 1 (Workflows)**: L1-L5 phases map directly into `workflows` (`drafting`, `planning`, `implementation`, `review`, and `pipelines`).
- **Group 2 (Assurance)**: Pure logic validation systems map into `assurance` (`validation`, `standards`, and topological `graph`).
- **Group 3 (Workspace)**: Physical environment representations map to `workspace` (`project`, `context`).
- **Group 4 (Interfaces)**: External system API triggers map into `interfaces` (`api`, `cli`).
- **Group 5 (Core)**: Internal state, orchestration, and executors map to `core` (`flow`, `loom`, `config`).
- **Group 6 (Infrastructure)**: External network mappings map to `infrastructure` (`llm`).

The system heavily utilizes `tach.toml` to enforce architectural imports across implicit namespace
packages. Changing root folders will forcibly break all internal `import src.specweaver.<app>`
syntaxes natively.

### Blueprint References
This refactoring directly reflects the `context.yaml` topological layering principles detailed in
`docs/architecture/architecture_reference.md` and aligns closely with clean Domain-Driven Design
(DDD). 

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Relocate L1-L5 Phases | System | Relocates directories `drafting`, `planning`, `implementation`, and `review` | Target paths reside correctly inside `src/specweaver/workflows/` |
| FR-2 | Relocate Assurance Bounds | System | Relocates pure-logic discovery `validation` and `standards` | Target paths reside correctly inside `src/specweaver/assurance/` |
| FR-3 | Relocate Workspace Bounds | System | Relocates physical project states `project` and `context` | Target paths reside correctly inside `src/specweaver/workspace/` |
| FR-4 | Relocate API Endpoint Bounds | System | Relocates exterior entry-points `cli` and `api` | Target paths reside correctly inside `src/specweaver/interfaces/` |
| FR-5 | Relocate Core Execution Suite | System | Relocates `flow`, `loom`, and `config` | Target paths reside correctly inside `src/specweaver/core/` |
| FR-6 | Relocate Infrastructure Adapters | System | Relocates the `llm` domain | Target paths reside correctly inside `src/specweaver/infrastructure/` |
| FR-7 | Mirror Unit and Integration Tests | System | Restructures `tests/unit/` and `tests/integration/` to identically match the 6 macro-domains over in `src/` | 1:1 structural parity between tests and code |
| FR-8 | Restructure E2E Test Suite | System | Restructures `tests/e2e/` from a flat tree into explicit business capability folders (by feature or story) | `tests/e2e/` map to features, not python files |
| FR-9 | Update Global Python Imports | System | Sweeps `src/` and `tests/` updating absolute Python import paths `specweaver.*` | Files natively resolve their dependencies inside the new domains |
| FR-10 | Adjust Architecture Topology Engine | System | Sweeps `tach.toml` and internal architecture graphs | Boundaries accurately describe the 6 macro-domains |
| FR-11 | Relocate Design Documents | System | Moves `docs/architecture/*` into `docs/architecture/` and permanently removes the empty `docs/proposals/design` paths | Design documents reside accurately within `architecture` |
| FR-12 | Relocate Roadmap Folder | System | Moves the entire `docs/roadmap/` directory up into `docs/roadmap/` | Project roadmap structures are cleanly elevated out of proposals |

### What the twelve FRs are, and how they are proven (2026-08-17, `INT-US-01-SF02-MIG`)

Every row here has the form *"directory X now lives at Y"*. None had a test, and the reason is
structural rather than negligent: **a completed move leaves nothing running to observe.** What it does
leave is a shape, and a shape is falsifiable — put a package back where it was and the assertion fails.
`tests/unit/test_macro_domain_layout.py` is that assertion, and each of its guards was verified by
mutating the tree: `workflows/review` moved back to the top level, a new flat e2e file, a stray test
directory, `tach.toml` renamed off a macro-domain. All four fail.

**The guards carry enumerated exceptions, never counted ones.** Where an FR is partly true the
exception is a *named path*. A count absorbs the next violation in silence — which is precisely what
`test_tach_architectural_boundaries` did for three months at `fail_count <= 95`, found and fixed the
same day as this. A named list absorbs nothing: a fourth stray directory fails, a fifth flat e2e file
fails.

### Three FRs describe a tree that is not there

**FR-5's `loom` clause is wrong, and struck.** It claims `flow`, `loom` and `config` moved into
`core/`. `flow` and `config` did. **There is no `loom` package anywhere in `src/`** — the Loom is the
top-level `sandbox/` package (hence `tests/integration/sandbox/test_loom_stack.py`), and it is
top-level by design, with `test_sandbox_is_grouped_by_feature_not_by_layer` already guarding its
internal shape. Asserting FR-5 as written would fail; asserting nothing would leave a reader hunting
for a `core/loom` that never existed. `test_the_loom_package_is_the_top_level_sandbox` pins the
correction in both directions — it also fails if a `core/loom` ever appears, which would mean this note
needs revisiting rather than the tree.

**FR-7 was not met, and is now closed (2026-08-17).** Four test directories had no `src/` counterpart:
`tests/unit/alembic`, `tests/integration/constitution`, `tests/integration/engine`, and `scripts` under
both tiers. Sorting them required reading what each actually tested rather than accepting the directory
name:

| Directory | What it holds | Disposition |
|---|---|---|
| `tests/integration/constitution/` | imports `workspace.project.constitution` and `.scaffold` — an ordinary test of `workspace.project`, filed under an invented top-level name | moved to `tests/integration/workspace/project/` |
| `tests/integration/engine/` | imports `core.flow.handlers.{arbiter,decompose,run_context}` — handler injection pathways | moved to `tests/integration/core/flow/handlers/` |
| `tests/unit/alembic/` | loads a migration module **by path** from repo-root `alembic/versions/`; imports nothing from `specweaver` | kept — mirrors a repo-root directory |
| `scripts` (both tiers) | the dev gates in repo-root `scripts/` | kept — mirrors a repo-root directory |

So two were parity gaps and two were never gaps at all. **The bar for the exception list is that the
directory mirrors something real** — `alembic/` and `scripts/` both exist at the repo root and are not
product code, which is a different statement from "has no home".

A fifth was **deleted rather than excepted**: `tests/unit/graph_store/`, an empty `__init__.py` stranded
when `graph/core/store` moved. A leftover is the restructure's own unfinished business, not an exception
to it.

`alembic`'s test is the one that could not have moved regardless: it computes its target as
`Path(__file__).parent.parent.parent.parent / "alembic" / "versions" / ...`, so its position in the tree
is load-bearing — the same hidden dependency FR-8's move hit in `test_cli_colour_e2e.py`, and a reason
to leave it where it correctly is.

**FR-8 was half met, and is now closed (2026-08-17).** It claims `tests/e2e/` was restructured *from* a
flat tree *into* capability folders. For a while both existed side by side: `capabilities/` with seven
domains, and beside it four loose test files and five layer-shaped directories (`core`, `flow`,
`interfaces`, `sandbox`, `scripts`).

**Sixteen files moved**, and two capability folders were added — `interfaces` and `sandbox`, both of
which mirror a `src/` macro-domain that `capabilities/` had no home for:

| From | To | Why |
|---|---|---|
| `test_cli_bootstrap_e2e.py`, `core/config/test_config_db_across_processes_e2e.py`, `core/flow/test_pipeline_hydration.py`, `core/flow/test_resume_after_failure_journey_e2e.py`, `capabilities/test_cli_lineage_e2e.py` | `capabilities/core/` | config bootstrap and routing, pipeline hydration and resume, lineage — all `core/` |
| `interfaces/test_cli_colour_e2e.py`, `interfaces/test_implement_usage_journey_e2e.py`, `test_cli_decentralized_e2e.py` | `capabilities/interfaces/` | journeys through the CLI surface itself |
| `sandbox/test_executor_e2e.py`, the three worktree-isolation journeys, `flow/test_cpp_flow.py` | `capabilities/sandbox/` | the executor, worktree isolation, and the polyglot code-structure atom — `test_cpp_flow.py` was filed under `flow/` but drives a `read_symbol` intent, not a pipeline |
| `test_logging_e2e.py`, `capabilities/test_provider_cli_e2e.py` | `capabilities/infrastructure/` | joins the two logging journeys already there; multi-provider is the LLM adapter |
| `test_polyglot_validation_e2e.py` | `capabilities/assurance/` | validation |

**`tests/e2e/scripts/` stays, and it is not a leftover.** It drives the repo's own dev tooling — the
mutation corpus CLI and the nightly timer — which are not product capabilities and have no capability
folder to belong to. That is the same reason `scripts` is excused from the src-mirror check, and it is
recorded as `E2E_NON_CAPABILITY_DIRS` rather than as a remainder.

The guard is now unconditional: `E2E_FLAT_REMAINDER_FILES` is empty, so a loose file at the tier root is
a **failure** rather than something to add to an exception list. It also asserts that every capability
folder mirrors a `src/` macro-domain, so "by capability" cannot drift back into "by whatever seemed
handy". 216 e2e tests pass, unchanged in number.

**One move needed a code change, which is why a restructure is not just `git mv`.**
`test_cli_colour_e2e.py` computed the repo root as `Path(__file__).resolve().parents[3]` and passed it as
`cwd` to a subprocess. One directory deeper, that resolves to `tests/e2e/`. It now walks up to the
directory holding `pyproject.toml`. A hardcoded ancestor index is a silent dependency on a file's
position in the tree — exactly the thing this FR moves.

**FR-9 was already fully true**: zero imports anywhere in `src/` or `tests/` name a pre-restructure
path. It is the only one of the twelve that needed nothing.

One note on instrument choice, because the first attempt got it wrong. The import sweep reads the
**AST**, not the text. A regex over source flagged `test_runner_architecture.py`, which writes
`from specweaver.llm import Client` into a temp file inside a triple-quoted string to exercise the
forbids checker. That is fixture data, and a text match cannot tell it from a real import of a package
deleted three restructures ago.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Regression Integrity | 3,884 total test cases natively MUST pass under execution. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-2 | Architectural Viability | `tach check` MUST yield 0 architectural domain drift validations. **[proof: arch — tach/lint gate, not pytest]** |
| NFR-3 | File Integrity | 0 Loss of files, configs, logic, or models during physical move (Data Retention 100%). |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Tach | Latest | `tach.toml` check | Yes | Structural constraints natively must be updated manually matching Python absolute domains. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Retain UUID UUID mapping within Tests | Prevents test regressions | No |

## Developer Guides Required

Evaluate if this feature introduces a new sub-system, paradigm, or extension layer that requires a Developer Guide for onboarding engineers.

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Architecture Bounds | Update Module Map structure inside Architecture Reference | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-01: Domain & Documentation Realignment (File Refactoring & Path Update)
- **Scope**: Physically migrates Source directories to the 6 macro-domains, structures `tests/`, and patches all Python absolute imports in parallel. Addresses documentation moves.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-11, FR-12]
- **Inputs**: Current `src/specweaver/*` flat mapping.
- **Outputs**: 4 new macro-domains holding accurately remapped imports.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3.26a/feature_3.26a_sf01_implementation_plan.md

### SF-02: Boundary Enforcement (Tach Matrix Matrix)
- **Scope**: Repairs the broken architectural test boundaries (Graph & Tach).
- **FRs**: [FR-10]
- **Inputs**: Updated namespace boundaries.
- **Outputs**: Valid `tach.toml` resulting in flawless `tach check` and 3884 passing execution tests.
- **Depends on**: [SF-01]
- **Impl Plan**: docs/roadmap/phase_3/feature_3.26a/feature_3.26a_sf02_implementation_plan.md

## Execution Order

1. SF-01 (No deps — Refactor file systems and strings first to repair IDE errors).
2. SF-02 (Depends on SF-01 — Locks boundary validation matrix post-file move).

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Domain File Realignment | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Boundary Matrix Sync | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Feature complete. Ready for dogfood + merge.
**Next step**: Proceed to next roadmap item.
