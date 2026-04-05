# Implementation Plan: Dynamic Risk-Based Rulesets (DAL) [SF-3: Validation Override Consolidation]
- **Feature ID**: 3.20b
- **Sub-Feature**: SF-3 — Validation Override Consolidation (Cleanup)
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_20b/feature_3_20b_design.md
- **Design Section**: §5 Sub-Feature Decomposition → SF-3
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_20b/feature_3_20b_sf3_implementation_plan.md
- **Status**: IMPLEMENTED

## Goal
Strip the legacy SQLite `validation_overrides` tables completely out of the system. Force all threshold boundaries to route strictly through our new DAL Impact Matrices and rule sub-pipeline inheritance. Deprecate CLI write access to validation rule tuning in favor of declarative files (`dal_definitions.yaml` / `.specweaver/pipelines/*.yaml`).

## HITL Design Decisions
1. **Hard Deletion (Option A):** Execute a hard `DROP TABLE` migration (Schema V14) to eliminate `validation_overrides` instantly. No YAML data migration tool required, preventing massive legacy technical debt since there are no active production customers yet.
2. **Read-Only CLI UX (Option B):** Delete all writing/modifying commands from the CLI (`set`, `reset`, `clear`). Keep the list commands specifically for viewing/monitoring what rules the engine is actively routing with.

## Proposed Changes

### `src/specweaver/config/_schema.py`
- [NEW] Add `SCHEMA_V14` string containing: `DROP TABLE IF EXISTS validation_overrides;`.

### `src/specweaver/config/database.py`
- [MODIFY] Append `_schema.SCHEMA_V14` to the active migrations deployment list.
- [MODIFY] Scan class docstrings and remove any commentary mentioning `validation_overrides`.

### `src/specweaver/config/_db_extensions_mixin.py`
- [DELETE] Method `set_validation_override()`.
- [DELETE] Method `get_validation_overrides()`.
- [DELETE] Method `clear_validation_override()`.
- [DELETE] Any embedded dependencies on these removed tables.

### `src/specweaver/cli/config.py`
- [DELETE] Subcommand `sw config validation set`.
- [DELETE] Subcommand `sw config validation reset`.
- [DELETE] Subcommand `sw config validation clear`.
- [MODIFY] Subcommand `sw config list` (or `validation list`). Refactor the display rich-table code: since it can't draw from `db.get_validation_overrides()` anymore, adapt it to load the project's base Pipeline + any domain profile modifications via the active `ValidationSettings`/`pipeline_builder` logic to provide read-only monitoring.

### Test Payload (Deprecation & Refactoring)
- **Delete Tests:** Completely delete `tests/unit/config/test_validation_overrides.py` as CRUD operations are entirely eliminated. Furthermore, locate and delete any active unit tests tracking `cli/config.py` rules parameters (`tests/unit/cli/test_cli_config.py` routines dealing with set/reset commands).
- **Refactor `test_database_migrations.py`:** Update V6 through V13 cascade tests heavily since they assert conditions against `get_validation_overrides()`. Rewrite the V14 test specifically to assert that the table does not exist inside `.schema`.
- **Refactor `test_profile_cascade.py` & `test_domain_profile_e2e.py`:** Remove all assumptions that Domain Profile assignments auto-generate or track rows inside `validation_overrides`.

## Verification Plan
1. Execution of full Pytest suite guarantees 0 `OperationalError (no such table: validation_overrides)` from cascading systems.
2. Verify `sw config validation list` does not panic and natively lists pipeline rules.
