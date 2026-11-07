# Implementation Plan: The Database Is Opened Three Ways [SF-04: One copy of each block]
- **Feature ID**: TECH-090
- **Sub-Feature**: SF-04 — One copy of each block
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_sf04_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-13 and FR-14. After SF-04, `workspace/store.py` is three files with one reason to change each,
`specweaver.db`'s step 1 names the memory tables it creates, `flow_artifact_events` has one
writer, and 11 of the 12 clones in the code this ticket touched are gone from the duplication
baseline (86 → 75). The twelfth is import lines and stays (Q2). No behaviour changes: the schema
comparison (FR-6), the CLI and the API answer as before.

## The 12 clones (measured 2026-11-07, `scripts/baselines/duplication.json`)

| # | Where | Lines | What is copied | Removed by |
|---|---|---|---|---|
| 1 | `workspace/store.py` `get_project` ↔ `list_projects` | 16 | a project row → dict | one `_project_dict(row)` |
| 2 | `workspace/store.py` `get_standards` ↔ `get_standard` | 14 | a standard row → dict | one `_standard_dict(row)` |
| 3 | `workspace/memory/store.py` `Epic` ↔ `Task` | 7 | the `project_name` foreign-key column | one column factory |
| 4 | `workspace/memory/store.py` `StateTransition` ↔ `Defect` | 8 | the `task_id` foreign-key column | one column factory |
| 5 | `core/flow/store.py` `get_artifact_history` ↔ `get_children` | 19 | an event row → dict | `FlowRepository` deleted (Q1) |
| 6 | `core/flow/store.py` ↔ `graph/lineage/store/lineage_repository.py` | 10 | the artifact-event checks | `FlowRepository` deleted (Q1) |
| 7–9 | `api/v1/pipelines.py`: 4 routes | 15–22 | open the state store, load the run or 404, parked or 409 | `_run_or_404`, `_parked_or_409` |
| 10 | `api/v1/projects.py` `delete_project` ↔ `use_project` | 12 | load the project or 404 | `_project_or_404(repo, name)` |
| 11 | `core/flow/engine/display.py` ↔ `api/event_bridge.py` | 10 | a runner event → JSON record | one `event_record(event, **kwargs)` in `core/flow/engine` |
| 12 | `api/v1/constitution.py` ↔ `api/v1/standards.py` | 10 | the module header and imports | stays: no code copy (Q2) |

## Commit boundaries

### CB-1 (interior): `workspace/store.py` split, memory tables named — FR-13, clones 1–4

**Tests first:**
- `tests/unit/workspace/test_store_split.py`: `workspace.models` holds `Base`, `Project`,
  `ActiveState`, `ProjectStandard` and does no I/O; `workspace.lookups` holds the 5 sync lookups;
  `workspace.store` holds `WorkspaceRepository` and no model. Red: the modules do not exist.
- `tests/unit/core/config/test_no_side_effect_imports.py`: no `import … # noqa: F401` of a store
  in `src/`. Red today: `db_bootstrap.py:13`.
- That step 1 still creates the 5 memory tables is proven by FR-6's schema comparison
  (`test_config_db_steps.py`), which fails on a missing table. Mutant: `MEMORY_TABLES` left out of
  step 1.
- Clones 1–4 are moves, guarded by the existing repository and memory tests and FR-6's schema
  comparison. Mutants: a wrong key in `_project_dict`; the `ondelete` of the factory column
  changed.

**Then the code:**
1. `tests/fixtures/db_utils.py` gains `user_version(path)` and `set_user_version(path, n)`; the 4
   test files from SF-03 use them (their copies go).
2. `workspace/models.py` (models), `workspace/lookups.py` (sync lookups); `workspace/store.py`
   keeps the repository. Importers change by script, as in SF-02 CB-1; no re-export.
3. `workspace/memory/store.py` imports `Base` from `workspace.models` and exports
   `MEMORY_TABLES`; `db_bootstrap` step 1 creates the workspace tables and `MEMORY_TABLES` by
   name, and the side-effect import goes.
4. `_project_dict`, `_standard_dict`; the two memory column factories.
5. `--update-baseline` drops clones 1–4.

### CB-2 (interior): one artifact-event repository, one event record — clones 5, 6, 11

**Tests first:**
- `tests/integration/graph/lineage/test_one_artifact_event_writer.py` (Q1): a pipeline step's
  lineage event (`log_artifact_event` in `core/flow/handlers/artifact_lineage.py`) is written
  through `LineageRepository` into `specweaver.db`, and `sw lineage` reads it back (history and
  children). Red today: the handler writes through `FlowRepository`.
- `tests/unit/test_one_writer_per_table.py`: `flow_artifact_events` appears in `src/` only in
  `graph/lineage/store/` (the SQL) and as `ArtifactEvent.__tablename__` in `core/flow/store.py`
  (the model step 1 creates), and no class but `LineageRepository` defines `log_artifact_event`.
  Red today: `FlowRepository`.
- The 8 handler unit tests that patch `core.flow.store.FlowRepository` patch
  `graph.lineage.store.lineage_repository.LineageRepository` instead.
- `tests/integration/core/flow/engine/test_cli_and_api_event_records_agree.py`: the NDJSON
  display and the event bridge give the same record for the same event (step start, step end with
  a result, run end). A seam test: both halves pass alone today.

**Then the code:**
1. The handler writes through `LineageRepository(context.db.path)`; a failure stays logged at
   exception level and the step goes on, as today.
2. `FlowRepository` is deleted; `ArtifactEvent` and `core.flow.store.Base` stay, because step 1
   creates the table from that model.
3. `event_record(event, **kwargs)` in `core/flow/engine/` (the two copies are identical today);
   the NDJSON display and the event bridge call it.
4. `core.flow.handlers` gains the `graph.lineage` edge (tach, `context.yaml`); baseline update.

**Mutants:** the handler writes nothing; `event_record` drops `run_status`.

> [!WARNING]
> Ten handler unit-test files pass `db=MagicMock()`. `context.db.path` is then a mock, and
> `open_sqlite` must not turn it into a file in the working folder. `os.fspath` of a `MagicMock`
> raises `TypeError`, which the handler logs; check `git status` shows no stray file after the
> suite at this boundary.

### CB-3 (closes SF-04, HITL): the API routes — clones 7–10, 12; FR-14 guard

**Tests first:**
- `tests/unit/scripts/test_touched_code_has_no_clones.py`: no baseline entry names a file of
  FR-14's list, except the one named import-only pair. Red until the baseline is re-frozen. Mutant: put one clone back → the duplication
  gate fails as a new clone.
- The routes keep their answers: existing API tests for `GET /runs/{id}`, `/log`, `resume`,
  `gate`, `DELETE /projects/{name}`, `POST /projects/{name}/use` (404, 409). Mutants: the 404 in
  `_run_or_404`; the 409 in `_parked_or_409`; the 404 in `_project_or_404`.

**Then the code:** the three helpers; baseline update; the README duplication sentence, if any.

## Research Notes

- `scripts/check_duplication.py`: a clone's key includes a hash of its text, so a moved clone is a
  new clone. Remove a clone before moving its file. Removals are re-frozen with
  `--update-baseline`.
- Memory models share `workspace.store.Base.metadata`; their tables exist only because
  `db_bootstrap.py:13` imports `workspace.memory.store` for its side effect.
- `FlowRepository` (`core/flow/store.py`, async ORM) and `LineageRepository`
  (`graph/lineage/store/lineage_repository.py`, sync SQL) both write `flow_artifact_events`, with
  the same three methods. The lineage handler (`core/flow/handlers/artifact_lineage.py:100`) uses
  the first; `sw lineage` (`graph/interfaces/cli.py:157`, `:180`) the second.
  `LineageRepositoryProtocol` lives in `graph/lineage/repository.py`.
- `workspace.store` is referenced by 75 files (src, tests, scripts, docs).
- Tach: `core.flow.handlers` does not depend on `graph.lineage` today; Q1 A adds that edge
  (handler → adapter, downward). `graph.lineage` depends only on `infrastructure.database`.

## Architecture (Phase 3)

- New files stay inside `specweaver.workspace` (one tach module): no new edge.
- Q1 A: `core.flow.handlers` → `graph.lineage`; no cycle (`graph.lineage` → database only).
- `event_record` in `core.flow.engine`: `interfaces.api` already depends on it.

## Decisions (Phase 4)

- **Q1** `flow_artifact_events` gets one writer: `graph.lineage`'s `LineageRepository`;
  `FlowRepository` is deleted `[agreed 2026-11-07]`.
- **Q2** The import-only clone of `constitution.py` and `standards.py` stays; FR-14 records it
  `[agreed 2026-11-07]`.
- **Q3** `workspace/models.py`, `workspace/lookups.py`; `workspace/store.py` keeps the repository
  `[agreed 2026-11-07]`.

## Consistency and red/blue (Phase 5), 2 cycles

- Every FR of SF-04 has a test: FR-13 (`test_store_split.py`, `test_no_side_effect_imports.py`,
  FR-6's comparison), FR-14 (`test_touched_code_has_no_clones.py`, `test_one_writer_per_table.py`,
  the two seam tests). No NFR changes; NFR-1 (no data lost) holds because no schema changes.
- Fixed in the plan: a planned subprocess test for the memory tables proved nothing, because the
  step imports `MEMORY_TABLES` from the memory store; FR-6's comparison is the proof. The
  one-writer guard first counted the model's `__tablename__` as a writer; it now allows it.
- Accepted: the handler is async and `LineageRepository` is sync, so a lineage write blocks the
  event loop for one small insert, as `StateStore` already does.
- The two event serializers are identical today (`display.py:364`, `event_bridge.py:99`); the seam
  test keeps them one.
- No mutant corpus names `core/flow/store.py`, so deleting `FlowRepository` stales none.
- Agent handoff: the 75 references to `workspace.store` change by script; the script and its
  count go in the CB-1 walkthrough, as in SF-02 CB-1.
