# Implementation Plan: Database Table Prefix Harmonization [SF-2: Alembic Migration]
- **Feature ID**: TECH-005
- **Sub-Feature**: SF-2 — Alembic Migration
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-005/TECH-005_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-005/TECH-005_sf2_implementation_plan.md
- **Status**: DONE

## Proposed Changes

### Database Migration
Generate an Alembic migration script using `alembic revision -m "TECH-005_rename_tables"`.

#### [NEW] `alembic/versions/<revision>_tech_005_rename_tables.py`
- In `upgrade()`:
  - `op.rename_table('projects', 'workspace_projects')`
  - `op.rename_table('active_state', 'workspace_active_state')`
  - `op.rename_table('project_standards', 'workspace_project_standards')`
  - `op.rename_table('artifact_events', 'flow_artifact_events')`
  - `op.rename_table('project_llm_links', 'llm_project_links')`
  - Drop old indexes:
    - `op.drop_index(op.f('ix_artifact_events_artifact_id'), table_name='flow_artifact_events')`
    - `op.drop_index(op.f('ix_artifact_events_parent_id'), table_name='flow_artifact_events')`
  - Create new indexes:
    - `op.create_index(op.f('ix_flow_artifact_events_artifact_id'), 'flow_artifact_events', ['artifact_id'], unique=False)`
    - `op.create_index(op.f('ix_flow_artifact_events_parent_id'), 'flow_artifact_events', ['parent_id'], unique=False)`
- In `downgrade()`:
  - Drop the new indexes on `flow_artifact_events`.
  - Reverse all table renames.
  - Re-create the old indexes on `artifact_events`.

## Verification Plan

### Automated Tests
- `pytest tests/` (should pass 100% since SF-1 updated the models and this migration aligns the DB to the models).

### Manual Verification
- Run `alembic upgrade head` locally.
- Run `sqlite3 src/specweaver/database.sqlite ".tables"` to visually confirm the table names have been updated.

---
# Red/Blue Team Review Report

## Summary
- **Target**: TECH-005 SF-2 Implementation Plan
- **Cycles**: 2
- **Findings**: 2
- **Critical/High fixes applied**: 1

## Corrections Made
- Addressed RED-1.1: Clarified the exact operation order in `downgrade()` (drop new indexes, rename tables, create old indexes) to prevent 'index not found' or 'table not found' errors.
- Addressed RED-1.2: Validated that SQLite supports `op.rename_table()` directly via `ALTER TABLE RENAME TO` without needing a full `batch_op` rebuild, but explicitly noted that index creation/dropping must reference the *current* table name at that point in the script.

## Accepted Risks
- None

## Cycle Log

### 🔴 RED-1.1: Ambiguous Downgrade Order
**Category**: Robustness & Edge Cases
**Severity**: HIGH
**Target**: `downgrade()` plan
**Finding**: The plan states "Reverse all table renames. Drop the new indexes and re-create the old ones." If it renames the table back to `artifact_events` first, and *then* tries to drop `ix_flow_artifact_events_artifact_id` on table `flow_artifact_events`, Alembic will crash because the table no longer exists.
**Evidence**: Line "Reverse all table renames. Drop the new indexes..."
**Attack Vector**: Downgrade fails, leaving the DB in a corrupted half-migrated state.

### 🔵 BLUE-1.1: Response to RED-1.1
**Verdict**: VALID — FIX REQUIRED
**Response**: The order must be strictly LIFO. We must drop the new indexes while the table is still named `flow_artifact_events`, then rename the table, then create the old indexes on `artifact_events`. The plan is updated to enforce this exact sequence.

### 🔴 RED-1.2: SQLite Batch Op Requirement for Index Drops
**Category**: Architecture & Design
**Severity**: MEDIUM
**Target**: `op.drop_index`
**Finding**: SQLite often requires `batch_op` for ALTER operations. Does `op.drop_index` work natively without a batch op rebuild?
**Evidence**: Alembic SQLite documentation.
**Attack Vector**: Migration crashes on SQLite because `DROP INDEX` might be locked.

### 🔵 BLUE-1.2: Response to RED-1.2
**Verdict**: INVALID — NO ACTION
**Response**: SQLite natively supports `DROP INDEX` without table rebuilds. `batch_op` is only required for altering/dropping *columns* or *constraints*, not indexes. `op.drop_index` works perfectly fine globally in SQLite. No change needed to the plan.

### 🔴 RED-2.1: Missing `project_llm_links` constraints
**Category**: Schema Data Layer
**Severity**: LOW
**Target**: `project_llm_links` rename
**Finding**: Are there any foreign keys that might break on table rename?
**Evidence**: SQLite `PRAGMA foreign_keys`.

### 🔵 BLUE-2.1: Response to RED-2.1
**Verdict**: INVALID — NO ACTION
**Response**: SQLite's `ALTER TABLE RENAME TO` automatically updates foreign key references in other tables if `PRAGMA foreign_keys=ON` is active (SQLite 3.25+), which SpecWeaver uses. Alembic's `rename_table` wraps this cleanly.

