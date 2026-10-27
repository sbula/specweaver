# Implementation Plan: The Layer Check Reports Clean While the Layers Are Broken [SF-01: The check sees every module]
- **Feature ID**: TECH-081
- **Sub-Feature**: SF-01 — The check sees every module
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf01_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-1 (no file outside a module), FR-2 (type-only imports checked), FR-3 (every wrong edge declared
`deprecated` and listed in the ledger with the FR that removes it), FR-5 (the ledger is true). NFR-2.
Kind `refactor`. No source file moves in SF-01; only `tach.toml`, the ledger and tests change.

## Research Notes

Read and measured 2026-10-27.

- **Simulation** (a copy of `src` and `tach.toml` in the scratchpad; the repo untouched): adding
  `root_module = "forbid"`, `ignore_type_checking_imports = false` and six modules
  (`commons` as `utility = true`, `assurance.graph`, `workflows.scenarios`, `workflows.evaluators`,
  `_version`, `telemetry_logger`, each `depends_on = []`) gives **44 undeclared imports on 28 edges and
  15 interface errors**. `commons` as a utility module costs no edge (the 119 earlier errors vanish).
- **The 15 interface errors** are type-only imports of names not in an `[[interfaces]]` block:
  `infrastructure.llm.adapters.base.LLMAdapter` (7 files), `workspace.context.analyzer_protocols.AnalyzerFactoryProtocol`
  (3), `assurance.validation.pipeline.ValidationPipeline` (2), `infrastructure.llm.prompt.profiles.RenderProfile`,
  `infrastructure.llm.prices.Price`/`PriceBook`, `assurance.validation.models.Rule`.
- **`tach` settings**: `root_module`, `ignore_type_checking_imports` (top-level keys),
  `utility = true` (module), `depends_on = [{ path = "...", deprecated = true }]` (reported as `‼️`,
  never failed). Docs `configuration.md`, `deprecate.md`; `tach/extension.pyi:100-174`.
- **Existing tests**: `tests/unit/test_architecture.py` (tach paths exist). Ledger:
  `docs/architecture/06_lessons_and_future/known_boundary_violations.md`.
- **Already-declared wrong edges** (in `tach.toml` today, both directions of a loop): 10 domain
  CLIs → `interfaces.cli` (EP-9); `core.config.bootstrap` → `core.flow` (FR-16);
  `core.flow` → `workflows.drafting` (FR-13).

## The edges, sorted

The rule: an edge whose direction the design keeps is declared plainly; an edge a later FR removes is
declared `deprecated` and gets a ledger row naming that FR.

| Edge (source → target) | Imports | Declared as | Owner |
|---|---|---|---|
| `assurance.graph` → `graph`, `workspace.analyzers`, `workspace.context` | 1, 3, 2 | plain | — (the direction FR-17 keeps) |
| `assurance.standards` → `core.config`, `workspace.context` | 1, 2 | plain | — (AD-12) |
| `assurance.standards.interfaces` → `core.config` | 1 | plain | — |
| `core.config.interfaces`, `interfaces.cli` → `telemetry_logger`; `interfaces.cli` → `_version`; `telemetry_logger` → `core.config` | 1 each | plain | — |
| `core.flow`, `core.flow.interfaces`, `interfaces.run_setup` → `assurance.graph` | 3, 1, 2 | plain | — |
| `core.flow` → `workflows.scenarios` | 2 | plain | — (the generator stays a workflow) |
| `workflows.drafting`, `workflows.planning` → `workspace.context` | 1, 1 | plain | — (AD-12) |
| `workflows.evaluators` → `core.config`; `workflows.scenarios` → `infrastructure.llm` | 1, 2 | plain | — |
| `workspace.project`, `workspace.project.interfaces` → `assurance.graph` | 1, 1 | plain | — (CW-15: made visible) |
| `core.flow` → `workflows.evaluators` | 2 | deprecated | FR-10 (AD-6) |
| `sandbox` → `workflows.scenarios`, `workflows.evaluators`, `core.flow` | 7, 1, 1 | deprecated | FR-10 |
| `graph` → `assurance.graph` | 2 | deprecated | FR-17 |
| `infrastructure.llm`, `workflows.drafting`, `workflows.planning` → `assurance.graph` | 1 each | deprecated | FR-17 (`TopologyContext` to `commons`) |
| 10 domain CLIs → `interfaces.cli` | (declared today) | deprecated | FR-15 |
| `core.config.bootstrap` → `core.flow` | (declared today) | deprecated | FR-16 |
| `core.flow` → `workflows.drafting` | (declared today) | deprecated | FR-13 |

The 15 interface errors are type-only uses of real public types: each name is added to its module's
`[[interfaces]]` block (no new edge).

## Approach (pseudocode, ordered)

**CB-1 — the check sees every module (FR-1, FR-2, FR-3, FR-5)** — closes SF-01
1. Tests first (red): `tests/unit/test_architecture.py` gains
   a. `tach.toml` sets `root_module = "forbid"` and `ignore_type_checking_imports = false` (FR-1, FR-2);
   b. every file under `src/specweaver` falls in a registered module (FR-1; the same prefix walk the
      simulation used, so the test names the stray file);
   c. the set of `deprecated` edges in `tach.toml` equals the set of edges in the ledger's TECH-081
      rows, and each row names an FR of the design (FR-3);
   d. every `src/...` path in the ledger's "Where" column exists (FR-5).
2. `tach.toml`: the two settings; the six modules; the plain edges and the `deprecated` edges from the
   table; the 15 interface names.
3. The ledger: remove the stale rows (`:11` llm FIXED, `:12` validation→sandbox, `:14`
   `exclusions.py`, `:16-17` config→workspace/llm, `:18` `workspace/store.py`, the unregistered-`commons`
   row); add the `topology.py:219,302` I/O row and one row per deprecated edge group with its FR.
4. `python -m tach check` green, with the `‼️` lines naming every owed edge.

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| unit | the two settings are set | FR-1, FR-2 | neither is in `tach.toml` |
| unit | no file under `src/specweaver` is outside a module | FR-1 | `_version.py`, `telemetry_logger.py` and 4 packages are outside |
| unit | deprecated edges = ledger TECH-081 edges, each with a design FR | FR-3 | no deprecated edge exists |
| unit | every ledger `src/...` path exists | FR-5 | `src/specweaver/llm/prompt_builder.py` (`:11`) does not |
| arch | `tach check` passes and reports the owed edges | NFR-2 | (the gate) |

Mutants (into `TECH-081_mutants.json`): drop `root_module = "forbid"`; set
`ignore_type_checking_imports = true`; turn one `deprecated = true` edge plain; delete one ledger row.
Each must turn a test red.

The design's FR-4 (manifests ↔ `tach.toml`) is SF-02's; nothing here claims it.

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–4 | full suite green; `tach check` green; the four mutants killed; stage and stop (closes SF-01) |

## Documentation

The ledger itself (step 3). `docs/architecture/03_system_topology/*` change in SF-08 (design).

## Architecture Verification (Phase 3)

- No source file changes; `tach.toml` gains six modules. `commons` as `utility` matches its manifest
  (`consumes: []`, every layer may use it).
- Every plain edge keeps the direction the design's FRs keep; every edge the design removes is
  `deprecated`, so no wrong edge is legitimised (NFR-2: later SFs only remove).
- The tests read `tach.toml` and the ledger as files; no subprocess.

## Audit (Phase 2) and Consistency (Phase 5)

- No open question: the six modules and settings follow FR-1/FR-2 `[agreed 2026-10-27]`; the sort
  follows the design's FRs and ADs (approved 2026-10-27). A plain edge is a claim; the table above lists
  every one for approval.
- Red/Blue, 2 cycles:
  - R1 (MEDIUM) `workspace.project` → `assurance.graph` declared plain could hide a wrong edge. Blue:
    `assurance.graph` uses only `graph` and the `workspace` analyzers/context, never `workspace.project`,
    so no loop; `tach_sync` reads a topology to write rules, which is its job.
  - R2 (MEDIUM) `core.flow` → `workflows.scenarios` plain while FR-10 moves the models. Blue: after
    FR-10 `core.flow` still uses `ScenarioGenerator` there; the edge stays.
  - R3 (LOW) test (b) repeats what `root_module = "forbid"` enforces. Blue: it names the stray file in
    a pytest message and survives a tach upgrade that renames the key.
  - Cycle 2: no new finding.
