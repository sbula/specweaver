# C-VAL-03 SF-03 — Validation Override Consolidation (Cleanup)

**Status**: IMPLEMENTED · **FRs owned**: FR-5 — freedom-from-interference outsourced to the native
boundary linter through the QA runner, merged with per-file `forbids` (recorded 2026-08-17 under
`specweaver-dev` §3.2c, from `INT-US-25-SF01-MIG`) · Design:
[C-VAL-03_design.md](C-VAL-03_design.md) §5 Sub-Feature Decomposition → SF-03 · Feature ID 3.20b

## Goal

Remove the legacy SQLite `validation_overrides` tables. All thresholds route through the DAL impact
matrices and rule sub-pipeline inheritance. The CLI loses write access to rule tuning; tuning is
declarative (`dal_definitions.yaml` / `.specweaver/pipelines/*.yaml`).

## Changes

1. **`src/specweaver/config/_schema.py`** — [NEW] `SCHEMA_V14`: `DROP TABLE IF EXISTS validation_overrides;`.
2. **`src/specweaver/config/database.py`** — [MODIFY] append `_schema.SCHEMA_V14` to the migrations
   list; remove docstring mentions of `validation_overrides`.
3. **`src/specweaver/config/_db_extensions_mixin.py`** — [DELETE] `set_validation_override()`,
   `get_validation_overrides()`, `clear_validation_override()`, and anything depending on them.
4. **`src/specweaver/cli/config.py`**
   - [DELETE] `sw config validation set`, `sw config validation reset`, `sw config validation clear`.
   - [MODIFY] `sw config list` (or `validation list`): the rich table no longer reads
     `db.get_validation_overrides()`; it loads the base pipeline + domain profile changes via the
     active `ValidationSettings`/`pipeline_builder` logic, read-only.

## Tests

| Action | Target |
|---|---|
| Delete | `tests/unit/config/test_validation_overrides.py` (CRUD is gone); set/reset tests in `tests/unit/cli/test_cli_config.py` (`cli/config.py`) |
| Refactor | `test_database_migrations.py`: V6 through V13 cascade tests asserted on `get_validation_overrides()`; the V14 test asserts the table is absent from `.schema` |
| Refactor | `test_profile_cascade.py`, `test_domain_profile_e2e.py`: drop the assumption that domain profiles write `validation_overrides` rows |

Verification:
1. The full suite raises 0 `OperationalError (no such table: validation_overrides)`.
2. `sw config validation list` runs and lists pipeline rules.

## Decisions (audit, HITL)

| # | Decision | Why |
|---|---|---|
| 1 | **Hard deletion (Option A):** `DROP TABLE` migration (Schema V14); no YAML data-migration tool | No production customers yet, so no legacy data to carry |
| 2 | **Read-only CLI (Option B):** delete `set`, `reset`, `clear`; keep the list commands | Viewing which rules the engine routes stays useful |
