# Implementation Plan: Structural Refactoring of Workspace AST Module [SF-1: Workspace AST Directory Migration]
- **Feature ID**: TECH-02
- **Sub-Feature**: SF-1 — Workspace AST Directory Migration
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-02/TECH-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-02/TECH-02_sf1_implementation_plan.md
- **Status**: APPROVED

## Context
This sub-feature executes the physical directory migration of `workspace/ast/parsers` and `workspace/ast/adapters` into a unified `workspace/ast` boundary to enforce Domain-Driven Design. It also updates the manifest files (`context.yaml`) and exacts the explicit boundaries in `tach.toml`. 

> [!CAUTION]
> **COMMIT BOUNDARY ALERT**: SF-1 and SF-2 must be executed sequentially but squash-merged into a **SINGLE ATOMIC COMMIT**. Committing SF-1 independently will break the build due to orphaned import paths.

## Proposed Changes

### `src/specweaver/workspace/ast/`
We will create this new unifying parent boundary. (No `__init__.py` is used, as we rely on native Python namespace packages enforced by `tach`.)
#### [NEW] `src/specweaver/workspace/ast/context.yaml`
A lightweight manifest explicitly declaring the purpose of this folder: Unifying AST extraction (`parsers`) and translation (`adapters`). No hard `forbids` or `consumes` restrictions are necessary here, as it inherits from `workspace` and delegates specifics to its children.

### `tach.toml`
#### [MODIFY] `tach.toml`
- Inject the explicit architectural interface boundaries into the `modules` array:
  - `{ path = "src.specweaver.workspace.ast.parsers", depends_on = [] }`
  - `{ path = "src.specweaver.workspace.ast.adapters", depends_on = [] }`

### Directory Relocations (Git MV)
We will execute standard `git mv` commands to physically relocate the source and test directories:
- `src/specweaver/workspace/ast/parsers` -> `src/specweaver/workspace/ast/parsers`
- `src/specweaver/workspace/ast/adapters` -> `src/specweaver/workspace/ast/adapters`
- `tests/unit/workspace/ast/parsers` -> `tests/unit/workspace/ast/parsers`
- `tests/unit/workspace/ast/adapters` -> `tests/unit/workspace/ast/adapters`

### Manifest Namespace Updates
#### [MODIFY] `src/specweaver/workspace/ast/parsers/context.yaml`
- Update `name: parsers` to `name: ast.parsers`
- Update `module_name: "specweaver.workspace.ast.parsers"` to `module_name: "specweaver.workspace.ast.parsers"` (if present).

#### [MODIFY] `src/specweaver/workspace/ast/adapters/context.yaml`
- Update `name: adapters` to `name: ast.adapters`
- Update `module_name: "specweaver.workspace.ast.adapters"` to `module_name: "specweaver.workspace.ast.adapters"` (if present).

## Verification Plan

### Automated Tests
- `python -m pytest tests/unit/workspace/ast/`
  - Expected: The tests will execute and pass. If it reports `collected 0 items`, the test migration failed.
- `python -m pytest tests/unit/test_architecture.py`
  - Expected: The `test_tach_interfaces_map_to_valid_namespaces` test will pass, verifying our new `tach.toml` injections correctly map to the physical directories.

### Manual Verification
- N/A. All verification is handled by the automated test suite.

## Research Notes
- `tach.toml` did not previously have explicit rules for `workspace.parsers`. The addition of `ast.parsers` and `ast.adapters` into the root `modules` list is a new explicit constraint, dramatically improving the structural rigidity.
- Test paths must be explicitly moved. Moving `src/` without moving `tests/unit/workspace/...` will orphan the test suite and cause future developers to write tests in the wrong location.
