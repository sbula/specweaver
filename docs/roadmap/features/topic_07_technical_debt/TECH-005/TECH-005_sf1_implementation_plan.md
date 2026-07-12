# Implementation Plan: Database Table Prefix Harmonization [SF-1: Model Refactoring]
- **Feature ID**: TECH-005
- **Sub-Feature**: SF-1 — Model Refactoring
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-005/TECH-005_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-005/TECH-005_sf1_implementation_plan.md
- **Status**: COMPLETED

## Goal
Update all SQLAlchemy models and raw queries to use prefixed database table names (`workspace_projects`, `workspace_active_state`, `workspace_project_standards`, `flow_artifact_events`, `llm_project_links`).

## Proposed Changes

### `specweaver.workspace.store`
#### [MODIFY] [store.py](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/store.py)
- Change `__tablename__ = "projects"` to `__tablename__ = "workspace_projects"`.
- Change `__tablename__ = "active_state"` to `__tablename__ = "workspace_active_state"`.
- Change `__tablename__ = "project_standards"` to `__tablename__ = "workspace_project_standards"`.
- Update `ForeignKey("projects.name")` to `ForeignKey("workspace_projects.name")` for `workspace_active_state` and `workspace_project_standards`.

### `specweaver.infrastructure.llm.store`
#### [MODIFY] [store.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/store.py)
- Change `__tablename__ = "project_llm_links"` to `__tablename__ = "llm_project_links"`.

### `specweaver.core.flow.store`
#### [MODIFY] [store.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/store.py)
- Change `__tablename__ = "artifact_events"` to `__tablename__ = "flow_artifact_events"`.

### `specweaver.workspace.memory.store`
#### [MODIFY] [store.py](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/memory/store.py)
- Update `ForeignKey("projects.name")` to `ForeignKey("workspace_projects.name")` in `MemoryEpic`, `MemoryTask` classes.

### Tests
#### [MODIFY] [test_db_utils.py](file:///c:/development/pitbula/specweaver/tests/unit/core/config/test_db_utils.py)
- Update `assert "projects" in tables` to `assert "workspace_projects" in tables`.

#### [MODIFY] [test_cli_db_utils.py](file:///c:/development/pitbula/specweaver/tests/unit/core/config/test_cli_db_utils.py)
- Update `assert "projects" in tables` to `assert "workspace_projects" in tables`.

#### [MODIFY] [test_handover_persistence.py](file:///c:/development/pitbula/specweaver/tests/integration/core/flow/engine/test_handover_persistence.py)
- Update `Base.metadata.tables["projects"]` to `Base.metadata.tables["workspace_projects"]`.

#### [MODIFY] [test_cli_bootstrap_e2e.py](file:///c:/development/pitbula/specweaver/tests/e2e/test_cli_bootstrap_e2e.py)
- Update `assert "projects" in tables` to `assert "workspace_projects" in tables`.

> [!NOTE]
> Historical Alembic migrations (e.g. `037b85034bb0_init_monolith_schema.py`) will deliberately NOT be modified. Instead, SF-2 will create a new migration to rename the tables. Tests check the final schema.

## Verification Plan

### Automated Tests
- Run `pytest` on `tests/unit`, `tests/integration`, and `tests/e2e`. All tests must pass, and the schema checks will succeed on the final table state.

---
# Red/Blue Team Review Report

## Summary
- **Target**: TECH-005 SF-1 Implementation Plan
- **Cycles**: 2
- **Findings**: 1
- **Critical/High fixes applied**: 0 (1 clarification)

## Corrections Made
- Addressed RED-1.1: Clarified that historical Alembic migrations are left untouched.

## Accepted Risks
- None

## Cycle Log

### 🔴 RED-1.1: Historical Migrations
**Category**: Robustness & Edge Cases
**Severity**: LOW
**Target**: Tests and DB Schema
**Finding**: The plan does not explicitly address whether historical Alembic migrations referring to `projects` will be updated.
**Evidence**: `037b85034bb0_init_monolith_schema.py` contains `projects`.

### 🔵 BLUE-1.1: Response to RED-1.1
**Verdict**: VALID — FIX REQUIRED (Clarification)
**Response**: Added a `[!NOTE]` explaining that historical migrations are never modified. The new migration (in SF-2) will transition the state, and tests verifying the final DB state will see `workspace_projects`.
