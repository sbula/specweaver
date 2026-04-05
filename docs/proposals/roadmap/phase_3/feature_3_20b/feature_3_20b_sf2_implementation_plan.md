# Implementation Plan: Dynamic Risk-Based Rulesets (DAL) [SF-2: Fractal Resolution Engine]

- **Feature ID**: 3.20b
- **Sub-Feature**: SF-2 — Fractal Resolution Engine
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_20b/feature_3_20b_design.md
- **Status**: APPROVED

## Goal

Provide O(1) cached directory-tree walking to incrementally resolve the exact Design Assurance Level (DAL) of any target file. Instead of defaulting to project-wide settings, the engine will search up from the target file directory to locate the nearest `context.yaml` and parse its `operational.dal_level`. 
Additionally, manage the Global Fallback Default behavior: If no target file context exists, gracefully fallback to a DB-backed global threshold, seeded safely to the maximum security setting (DAL_A) upon setup.

## Architectural Decisions & HITL Responses (Merged)

1. **Resolution Engine Placement (Zero-Trust):** The resolution engine (`dal_resolver.py`) will live inside the `specweaver/config/` module, safely serving as a leaf node which `flow` handles correctly without cyclical dependency boundary violations.
2. **Orchestration Bridging:** The `ValidateSpecHandler` and `ValidateCodeHandler` (`flow/_validation.py`) will directly invoke the DAL lookup locally, check defaults if necessary, and manually map the DAL matrices into standard `apply_settings_to_pipeline()`.
3. **Boundary Condition (Root Detection):** The resolver will walk from the target file upward but aggressively halt precisely at the system `project_root` returning `None` instead of infinitely scanning outside the project.
4. **Configurable Default DAL:** If the scanner returns `None`, the Orchestrator will query the database for the newly supported `default_dal` field to use as the fallback. During project initialization, this field seeds to `DAL_A` (Flight-Critical) to ensure extreme governance adoption for new and legacy project onboarding.
5. **Config DB Scope:** Feature 3.5's massive Validation DB Overrides Cleanup is successfully quarantined to sub-feature **SF-3** to eliminate regression risks and preserve testability.

## Proposed Changes

### `specweaver/config/_schema.py` -> [COMPLETED]
- Increment DB Migrations adding `SCHEMA_V13` to augment table `projects` with `default_dal VARCHAR NOT NULL DEFAULT 'DAL_A'`.

### `specweaver/config/_db_config_mixin.py` & `database.py` -> [COMPLETED]
- Add `get_default_dal(project_name)` and `set_default_dal(project_name, dal)`.
- Register `SCHEMA_V13` inside `database.py` global migrations list.

### `specweaver/config/dal_resolver.py` -> [COMPLETED]
- Implement `DALResolver` class.
- Accepts `project_root: Path` in construction.
- Contains an internal `self._cache: dict[Path, DALLevel | None]` instance dictionary.
- Method `resolve(target_path: Path) -> DALLevel | None`: Walk `target_path.parents`, parsing `context.yaml` sequentially. Halts immediately and returns `None` upon breaking out of `project_root`. **NOTE:** If a `dal_level` string is found but is invalid (not in `DALLevel` enum), raise a `ValueError` immediately (Fail-Secure).
- *Deviation/Addition (Task 2)*: Implemented fail-safe resilience against malformed YAML structures to prevent `context.yaml` syntax errors from aborting traversal.

### `specweaver/flow/_validation.py` -> [COMPLETED]
- Update `ValidateSpecHandler.execute` and `ValidateCodeHandler.execute` to instantiate `DALResolver(context.project_path)`.
- Invoke `dal = dal_resolver.resolve(target)`.
- `if not dal:` execute `dal = context.db.get_default_dal()`.
- Fetch the specific risk constraints via `dal_settings = context.settings.dal_matrix.matrix.get(dal)`.
- If constraints exist, safely deep-merge them over the baseline `context.settings.validation` overrides using a pure python dictionary merge, and reconstruct a new `ValidationSettings` object.
- Finally, invoke `apply_settings_to_pipeline(pipeline, merged_settings)`.

### `specweaver/config/context.yaml` -> [COMPLETED]
- Expose `DALResolver` to project boundaries via explicit `exposes:` array modifications.

## Verification Plan

### Automated Tests
- `tests/unit/config/test_dal_resolver.py`: Ensure parsing of valid/invalid/missing `.yaml` structures, verify memoization performance against patches, and ensure strict `project_root` boundary cutoffs.
- `tests/unit/config/test_database.py`: Verify `SCHEMA_V13` SQLite schema migrations construct seamlessly natively across both fresh DB instances and upgraded instances.

### Pre-commit Validation
- Run `/pre-commit` workflow on completion to automatically run the 10-test validation battery, `tree-sitter` drift checks, type-checking, and styling logic.
