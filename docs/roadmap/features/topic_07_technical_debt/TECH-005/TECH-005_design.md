# Design: Database Table Prefix Harmonization

- **Feature ID**: TECH-005
- **Phase**: 6
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-005/TECH-005_design.md

## Feature Overview

Feature TECH-005 adds a strict domain-prefix naming convention to all database tables in the monolithic SQLite database.
It solves the risk of naming collisions as domain count grows by explicitly scoping table names to their bounded contexts.
It interacts with the SQLAlchemy models and Alembic migrations across `specweaver.workspace`, `specweaver.infrastructure.llm`, and `specweaver.core.flow` and does NOT touch any domain logic.
Key constraints: zero data loss during the migration, explicitly rename any indexes that contained the old table name.

## Research Findings

### Codebase Patterns
Existing modules (`specweaver.workspace`, `specweaver.infrastructure.llm`, `specweaver.core.flow`) have tables that lack bounded context prefixes. 
These tables must be renamed to align with the architectural standard set by `memory_` prefix. 
The renames are: `projects` -> `workspace_projects`, `active_state` -> `workspace_active_state`, `project_standards` -> `workspace_project_standards`, `artifact_events` -> `flow_artifact_events`, and `project_llm_links` -> `llm_project_links`. 
Existing tables like `llm_usage_log`, `llm_cost_overrides`, and `llm_profiles` already follow the convention and are left intact.
This change aligns with the `context.yaml` boundaries and does not duplicate any functionality.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Alembic | >=1.13.0 | `op.rename_table`, `op.execute` | pyproject.toml |
| SQLite | Any | `ALTER TABLE RENAME TO` | Environment |

### Blueprint References
This architectural standard was established during B-INTL-09 (Agent Memory Bank) with the `memory_` prefix pattern.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Rename workspace tables | System | Rename `projects`, `active_state`, `project_standards` to `workspace_projects`, `workspace_active_state`, `workspace_project_standards` | Tables accurately reflect their workspace bounded context. |
| FR-2 | Rename flow tables | System | Rename `artifact_events` to `flow_artifact_events` | Table accurately reflects its flow bounded context. |
| FR-3 | Rename llm tables | System | Rename `project_llm_links` to `llm_project_links` | Table accurately reflects its llm bounded context. |
| FR-4 | Update Models | System | Update all `__tablename__` directives in SQLAlchemy models to match the new names | Application logic maps to the correct new table names. |
| FR-5 | Update queries and references | System | Update all raw SQL queries and string-based ForeignKey references | All tests and queries execute without reference errors. |
| FR-6 | Rename Indexes | System | Explicitly rename any existing indexes tied to the old table names to match the new table names | Indexes remain functionally intact and clearly named. |
| FR-7 | Generate Migration | System | Generate an Alembic migration using `op.rename_table` for all renamed tables | The database schema is migrated safely. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Data Loss | Zero data loss during the Alembic migration. Data must be preserved exactly as it was. |
| NFR-2 | Test Integrity | 100% of existing tests must pass after the table renaming is applied. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Alembic | 1.13.0 | `op.rename_table` | Yes | SQLite handles `ALTER TABLE RENAME TO` safely for this operation. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Prefix Table Names | Resolves technical debt and prevents naming collisions in SQLite monolithic DB. | No |
| AD-2 | Rename `project_llm_links` to `llm_project_links` | The table resides in `specweaver.infrastructure.llm.store`, so it belongs to the `llm` boundary. | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| Schema migration | Low | Low. Standard Alembic functionality. |
| Refactoring queries | Medium | Low. Grep and replace is straightforward but needs comprehensive test validation. |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| Data Architecture | Domain isolation at schema level | High |
| Development Team | Prevents collision errors on simple table names like `projects` | Medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Data loss in SQLite migration | Low | High | Use Alembic's `rename_table`. SQLite natively supports this via `ALTER TABLE`. Run full test suite. |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| All existing queries | Hardcoded table names | Cleaner domain-aligned queries | Included in this feature |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| N/A | No new architecture introduced, simply enforcing existing standard. | N/A |

## Sub-Feature Breakdown

### SF-1: Model Refactoring
- **Scope**: Update `__tablename__` attributes, raw queries, and ForeignKeys across the codebase to use new prefixes.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5]
- **Inputs**: Existing SQLAlchemy models and queries.
- **Outputs**: Updated codebase with no compilation errors.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-005/TECH-005_sf1_implementation_plan.md

### SF-2: Alembic Migration
- **Scope**: Generate and apply the database schema migration via Alembic to rename tables and indexes.
- **FRs**: [FR-6, FR-7]
- **Inputs**: The updated SQLAlchemy models from SF-1.
- **Outputs**: A new Alembic migration script.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-005/TECH-005_sf2_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Model Refactoring | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Alembic Migration | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: TECH-005 is 100% COMPLETE.
**Next step**: Move to the next active epic on the master roadmap (e.g. TECH-009).

---
# Red/Blue Team Review Report

## Summary
- **Target**: TECH-005 Design Document
- **Cycles**: 2
- **Findings**: 3
- **Critical/High fixes applied**: 2

## Corrections Made
- Addressed RED-1.1: Clarified that `llm_usage_log`, `llm_cost_overrides`, and `llm_profiles` already follow the convention and are explicitly left intact.
- Addressed RED-1.2: SQLite `rename_table` handles table renames, but indexes referencing the old table name must be explicitly renamed. Added FR-6 to address this.
- Addressed RED-1.3: Fixed FR numbering drift in the Sub-Feature Breakdown section.

## Accepted Risks
- None

## Cycle Log

### 🔴 RED-1.1: Unmentioned LLM Tables
**Category**: Architecture & Design
**Severity**: MEDIUM
**Target**: FR List
**Finding**: `llm_usage_log`, `llm_cost_overrides`, and `llm_profiles` are identified in the DB but not addressed in FRs. The design should explicitly confirm they are correct and skip them.
**Evidence**: DB research lists them, FR table does not cover their disposition.

### 🔵 BLUE-1.1: Response to RED-1.1
**Verdict**: VALID — FIX REQUIRED
**Response**: The tables are correctly prefixed, but this should be explicitly documented. Added to Research Findings.

### 🔴 RED-1.2: Index Renaming in SQLite
**Category**: Robustness & Edge Cases
**Severity**: HIGH
**Target**: Alembic Migration NFRs
**Finding**: SQLite renames tables with `ALTER TABLE RENAME`, but indexes containing the table name may need explicit renaming to preserve convention.
**Evidence**: Alembic docs on SQLite `rename_table`.

### 🔵 BLUE-1.2: Response to RED-1.2
**Verdict**: VALID — FIX REQUIRED
**Response**: Added FR-6 to explicitly rename indexes to maintain naming convention consistency.

### 🔴 RED-1.3: Numbering Error
**Category**: Maintainability
**Severity**: LOW
**Target**: Sub-Feature Breakdown
**Finding**: Mentioned FR-8 in SF-1, but the table only went up to FR-6.
**Evidence**: Design document text.

### 🔵 BLUE-1.3: Response to RED-1.3
**Verdict**: VALID — FIX REQUIRED
**Response**: Renumbered FRs and mapped them correctly to the SF subsets.

---
*(End of Red/Blue Team Review Report)*
