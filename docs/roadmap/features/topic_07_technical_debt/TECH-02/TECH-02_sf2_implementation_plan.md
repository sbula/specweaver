# Implementation Plan: Structural Refactoring of Workspace AST Module [SF-2: Global Import Harmonization]
- **Feature ID**: TECH-02
- **Sub-Feature**: SF-2 — Global Import Harmonization
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-02/TECH-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-02/TECH-02_sf2_implementation_plan.md
- **Status**: APPROVED

## Context
This sub-feature executes the mass search-and-replace to update all import paths across the codebase from `specweaver.workspace.ast.parsers` to `specweaver.workspace.ast.parsers`, and `specweaver.workspace.ast.adapters` to `specweaver.workspace.ast.adapters`.
It also fixes any test files that might be referencing these paths.

## Proposed Changes

### Global Namespace Refactoring
We will execute a global replacement across the `src/` and `tests/` directories.
#### [MODIFY] All affected Python and YAML files
- Search: `specweaver.workspace.ast.parsers` -> Replace: `specweaver.workspace.ast.parsers`
- Search: `specweaver.workspace.ast.adapters` -> Replace: `specweaver.workspace.ast.adapters`

## Verification Plan

### Automated Tests
- `python run_unit_tests.py`
  - Expected: All unit tests pass, meaning no `ModuleNotFoundError` or `ImportError` occurs.
- `python run_integ_tests.py`
  - Expected: All integration tests pass.
- `python run_e2e_tests.py`
  - Expected: All E2E tests pass.

## Research Notes
- A simple string replacement is highly effective here because `specweaver.workspace.ast.parsers` is a highly specific, unique string that does not collide with other variables.
- We must ensure we cover `.yaml` files (e.g. `context.yaml` `consumes` lists) as well as `.py` files.
