# Implementation Plan: Each Entry Point Builds Its Run by Hand, and the API Gets Less [SF-01: One answer per lookup]
- **Feature ID**: TECH-077
- **Sub-Feature**: SF-01 — One answer per lookup
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_sf01_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-6 (archetype found one way), FR-9 (one project-root rule for validation), FR-10 (one lookup per
project question, one constitution limit). Kind `bugfix`. No dependency. NFR-4 applies.

## Research Notes

- **Archetype** (FR-6):
  - `RunContext._read_archetype` (`core/flow/handlers/run_context.py:244`) reads only
    `project_path / "context.yaml"`; used at `:209` (run record / prompt).
  - `archetype_pipelines.archetype_of(path, project_path)` (`:41`) uses
    `ArchetypeResolver(project_path).resolve(path)` — nearest `context.yaml` at or above `path`,
    bounded by the project root (`core/config/archetype_resolver.py:34`).
  - `context_assembler.evaluate_and_fetch_skeleton_context` (`:47`) takes
    `context.graph.topology.archetype`, else `"generic"`.
- **Project root in rules** (FR-9): rules get a `context` dict from `execute_validation_pipeline(...,
  context=...)` (`assurance/validation/executor.py:125-187`). Callers that know the root:
  `core/flow/handlers/validation.py:230`, `validation_hydrator.py:371`, `interfaces/api/v1/validation.py:123`,
  `assurance/validation/interfaces/cli.py:300`. Today the rules walk up from the file with no stop:
  - C02 (`c02_tests_exist.py:36`): every ancestor's `tests/` until the filesystem root.
  - C03 (`c03_tests_pass.py:98`): nearest `pyproject.toml` (the Python test runner's root), else
    the filesystem root.
  - C09 (`c09_traceability.py:96`): nearest of `pyproject.toml`, `package.json`, `.git`, `.specweaver`.
  - The hasher (`assurance/graph/hasher.py:32`) looks for `.git` only to place a `.gitignore`
    line — the git root, a different question; no change.
- **Project lookups** (FR-10):
  - "at this path": `workspace/store.py` `default_dal_at`, `project_name_at`, `domain_profile_at`
    (`:87-115`, each its own raw `db.connect()` query over all rows) and
    `_core.registered_project_at` (`interfaces/cli/_core.py:107`, async repo `list_projects`).
  - "name to root": `settings_loader.py:103` (async repo, `ValueError`), `_core.project_root`
    (`:99`, None), `workspace/project/interfaces/cli.py:106,276` (exits if missing),
    `assurance/standards/interfaces/cli.py:36` (exits if missing), `interfaces/api/v1/paths.py:88`
    (404). The existence checks differ on purpose per caller; the lookup itself is the duplicate.
  - "registered value with fallback" (FL-20): `core/flow/engine/naming.py:17` (folder name),
    `core/flow/handlers/scenario_store.py:19` (None), `core/flow/handlers/validation.py:38`
    (`DEFAULT_DAL`), `:540` (None) — each `try: db … except: warn; fallback`.
- **Constitution limit** (CW-20): `workspace/project/constitution_loading.py:22`
  `DEFAULT_MAX_CONSTITUTION_SIZE = 5120` and `workspace/store.py:55` `default=5120`. `tach`:
  `workspace` and `workspace.project` may not import each other; both may import `commons`.

## Decisions (Phase 4, user answered "all A" 2026-10-23)

1. FR-9: each rule keeps its purpose; all three share one walker that stops at the run's project
   root.
2. The lookups use the store's sync `db.connect()` queries; async callers wrap them in
   `asyncio.to_thread`.
3. The constitution limit lives in `commons`.

## Approach (pseudocode, ordered)

**FR-10 — lookups**
1. `workspace/store.py`: one `_project_row_at(db, root)` (the one query, resolved-path match);
   `default_dal_at`, `project_name_at`, `domain_profile_at` read from it. New
   `project_root_of(db, name) -> Path | None`.
2. `_core.registered_project_at` and `_core.project_root` call the store functions (decision 2);
   the async callers (`settings_loader`, `api/v1/paths.py`) call them through `asyncio.to_thread`.
   Each caller keeps its own answer for "missing" (exit, 404, `ValueError`, None).
3. `core/flow/engine/registered.py`: `registered(context, read, default)` — run `read(db, root)`,
   on any error log a WARNING and return `default`; the four FL-20 callers use it.
4. `commons`: `DEFAULT_MAX_CONSTITUTION_SIZE`; `constitution_loading` and the store column default
   import it.

**FR-6 — archetype**
5. `_read_archetype` and the context assembler's fallback use `ArchetypeResolver(project_path)`:
   the run context asks for the spec's folder, the assembler for each target file; a topology
   archetype no longer overrides the file's own `context.yaml`.

**FR-9 — project root in rules** (decision 1)
6. The four callers pass `context={"project_root": root}`; C02, C03, C09 read it.
7. One walker `walk_up(path, stop)` (in `assurance/validation`), used by all three, never goes above
   `stop` (the project root; the filesystem root when no root is known).

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/workspace/store.py` [MODIFY] | one row lookup; `project_root_of`; limit from `commons` |
| `src/specweaver/interfaces/cli/_core.py`, `core/config/bootstrap/settings_loader.py`, `interfaces/api/v1/paths.py`, `workspace/project/interfaces/cli.py`, `assurance/standards/interfaces/cli.py` [MODIFY] | use the store lookups |
| `src/specweaver/core/flow/engine/registered.py` [NEW] | `registered(context, read, default)` |
| `src/specweaver/core/flow/engine/naming.py`, `core/flow/handlers/scenario_store.py`, `core/flow/handlers/validation.py` [MODIFY] | use it |
| `src/specweaver/commons/limits.py` [NEW] | `DEFAULT_MAX_CONSTITUTION_SIZE` |
| `src/specweaver/core/flow/handlers/run_context.py`, `context_assembler.py` [MODIFY] | archetype by `ArchetypeResolver` |
| `src/specweaver/assurance/validation/project_root.py` [NEW] | `walk_up(path, stop)` |
| `c02_tests_exist.py`, `c03_tests_pass.py`, `c09_traceability.py` and the four executor callers [MODIFY] | the run's root |

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| FR-10 | integration | `tests/integration/workspace/test_one_project_lookup.py` [NEW] | a real DB: name, DAL, profile and root of a registered project (happy); a path spelled two ways is one project (boundary); no project there → None (degradation); a renamed folder / unknown name → None (hostile). **Agreement:** `_core.registered_project_at`, `store.project_name_at` and the API's root lookup answer alike. Red first: `project_root_of` absent |
| FR-10 | unit | `tests/unit/core/flow/engine/test_registered.py` [NEW] | value read (happy); no DB on the context → default (boundary); the read raising → WARNING and default (degradation) |
| FR-10 | unit | `tests/unit/commons/test_limits.py` [NEW] | the store column default and the loader default are the same object's value |
| FR-6 | integration | `tests/integration/core/flow/handlers/test_one_archetype.py` [NEW] | a nested `service/context.yaml` (`spring-boot`) under a root `generic`: the run context, the archetype pipelines and the assembler all answer `spring-boot` for a file in `service/` (agreement); no `context.yaml` → `generic` (boundary); an unreadable one → `generic` and a WARNING (degradation). Red today: the run context says the root's value, the assembler the topology's |
| FR-9 | unit | `tests/unit/assurance/validation/test_project_root.py` [NEW] | `walk_up` stops at `stop`, never above (hostile: a `tests/` above the project is not found); with no `stop` behaves as today |
| FR-9 | integration | `tests/integration/assurance/validation/test_rules_share_the_root.py` [NEW] | C02, C03, C09 in one pipeline with `project_root` given: a `tests/test_x.py` above the project root is not used (red today: C02 finds it) |

Mutants: FR-10 `_project_row_at` ignores path resolution; `registered` returns the read's error;
FR-6 `_read_archetype` back to the root file; FR-9 `walk_up` ignores `stop`.

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | FR-10: store lookups, callers, `registered`, the constant | tests green; FR-10 mutants killed; anchor check clean |
| CB-2 | FR-6: archetype | green; mutant killed |
| CB-3 | FR-9: project root. Closes SF-01: stops for the user's acceptance | green; mutant killed |

## Documentation

`docs/dev_guides` pages that name the old lookups or the archetype rule (grep at each boundary).

## Audit (Phase 2) — answered: all A, 2026-10-23

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | FR-9 "one rule": the three rules look for different things on purpose — C02 any `tests/` near the file, C03 the Python test runner's root (`pyproject.toml`), C09 the project root. One marker list would move C03's test runs in a monorepo of several Python packages. | A: keep each rule's purpose, but every walk shares one walker and stops at the run's project root (today they can climb to the filesystem root). B: one marker list for all three. | A — the real defect is climbing out of the project; B would break sub-package test runs | MEDIUM |
| 2 | DB style for the lookups. | A: the store's sync `db.connect()` queries (what the engine uses); async callers wrap them in `asyncio.to_thread`. B: the async repository everywhere. | A — the engine is sync; the async callers are two | LOW |
| 3 | Home of the constitution limit: `workspace` and `workspace.project` may not import each other. | A: `commons`. B: `core/config`. | A — both may import `commons` | LOW |

## Architecture Verification (Phase 3)

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| store lookups | `workspace` · adapter | DB reads (as today) | none | none | none new | projects | ok |
| `registered.py` | `core/flow/engine` | DB read via the context | none | none | `workspace` (allowed) | run inputs | ok |
| `limits.py` | `commons` | none | none | none | none | constants | ok |
| `project_root.py` | `assurance/validation` | filesystem stat | none | none | none | validation | ok |

No new module edge (the engine still never imports `workspace/project`), no cycle, no `tach.toml`
change. No CRITICAL architecture finding.

## Consistency Check and Red/Blue (Phase 5)

- **Coverage**: FR-10 (CB-1), FR-6 (CB-2), FR-9 (CB-3). NFR-4: each lookup keeps its caller's
  answer for "missing"; only the query is shared. NFR-2: the engine gains no `workspace/project`
  import (`registered.py` uses `workspace` and the context's DB).
- **Open questions**: none. All decisions are resolved and documented inline in the plan.
- **Handoff risk**: moving code drifts other corpora's mutants (TECH-076 lesson): run the anchor
  check (`.tmp/anchors.py`, every corpus `old` text found in its `file`) before every commit.
- **Architecture**: no new edge, no cycle; `commons` is importable by both `workspace` modules.
- **DDD/KISS/DRY/hexagonal/SoC**: one query per question; rules keep their own purpose.
- **Code detail limit**: no code block; steps are pseudocode.
- **Red/Blue**, 2 cycles:
  - R1 (MEDIUM) `asyncio.to_thread` with a sync SQLite connection. Blue: `Database.connect()` opens a
    new connection per call (`core/config/database.py:277`), so no connection crosses threads.
  - R2 (MEDIUM) the run context's archetype now follows the spec's folder, so a nested spec reports
    its own archetype in the run record. Blue: the point of FR-6.
  - R3 (MEDIUM) the assembler loses the topology's archetype when no `context.yaml` exists. Blue: the
    topology reads the same `context.yaml` files; with none, both say `generic`.
  - R4 (LOW) C02 no longer finds a `tests/` above the project root. Blue: the hostile case; a project's
    tests live inside it.
  - Cycle 2: no new finding. Below every threshold.
