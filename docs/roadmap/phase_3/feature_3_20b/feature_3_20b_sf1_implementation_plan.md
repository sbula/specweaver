# Implementation Plan: Dynamic Risk-Based Rulesets (DAL) [SF-1: DAL Schema & Pydantic Impact Matrix Merge]
- **Feature ID**: 3.20b
- **Sub-Feature**: SF-1 — DAL Schema & Pydantic Impact Matrix Merge
- **Design Document**: docs/roadmap/phase_3/feature_3_20b/feature_3_20b_design.md
- **Design Section**: §Sub-Feature Decomposition → SF-1
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_20b/feature_3_20b_sf1_implementation_plan.md
- **Status**: APPROVED

## Goal Description
Implement the core configuration layer for Mixed Criticality (DAL) execution. We will define the `DALLevel` enumeration (`DAL_A` through `DAL_E`) inside the fundamental `config/dal.py` module. Next, we will introduce a `DALImpactMatrix` schema inside the database or settings loader that maps these DAL levels to deep configuration overrides (disabling rules or tightening thresholds based on risk tier). The system will safely deep-merge user-defined `.specweaver/dal_definitions.yaml` over the standard internal profiles using `ruamel.yaml` before invoking Pydantic's strict schema validation.

## User Decisions (Phase 4 Audits Merged)
- **Deep Merge Strategy**: Pydantic's `SettingsConfigDict` lacks a native `deep_merge=True` parameter. To avoid fragile internal settings-source hacking, we rely on a custom, deterministic `deep_merge_dict()` helper in `config/settings.py` paired with `ruamel.yaml` for deserialization to correctly layer project-level `dal_definitions.yaml` configs on top of our system default configurations, validating the final flattened dictionary via `Pydantic` `ValidationSettings(**merged)`.
- **Architectural Boundary Safety**: To prevent circular dependencies, `DALLevel` relies exclusively on `config/dal.py` rather than `validation/models.py`. The `config` module natively sits strictly below everything (`consumes: []`).

## Proposed Changes

### [NEW] src/specweaver/config/dal.py
- Define `class DALLevel(enum.StrEnum):` 
  - `DAL_A = "DAL_A"` (Highest Risk / Aerospace-grade)
  - `DAL_B = "DAL_B"`
  - `DAL_C = "DAL_C"`
  - `DAL_D = "DAL_D"`
  - `DAL_E = "DAL_E"` (Lowest Risk / Startup Scripts)

### [MODIFY] src/specweaver/config/settings.py
- Add `from specweaver.core.config.dal import DALLevel`
- Create `class DALImpactMatrix(BaseModel):`
  - A mapping of `DALLevel` to `ValidationSettings` (`dict[DALLevel, ValidationSettings]`), allowing rules to be bypassed or made stricter based on risk.
- Ensure `ValidationSettings` fields correctly support `enabled: bool = True` explicitly to allow disabling specific rules. (e.g. `Rule_X: {"enabled": False}`).
- Implement a module-level pure logic string function: `deep_merge_dict(base: dict, overlay: dict) -> dict` 
  - Standard dictionary recursor: Updates primitive keys, deep-merges nested dicts.
- Modify `load_settings()` orchestration:
  - If `.specweaver/dal_definitions.yaml` exists, load it via `ruamel.yaml`.
  - Fetch default framework DAL definitions map (or construct an empty baseline).
  - Use `deep_merge_dict()` to merge project-specific DAL rulesets over the baseline.
  - Finalize hydration of the merged dictionary into Pydantic models to assert schema type-safety.

## Verification Plan

### Automated Tests
- Create `tests/unit/config/test_dal_merge.py`.
- Write unit tests targeting `deep_merge_dict()` to guarantee that dictionary keys present in the overlay overwrite base keys, while unmentioned base keys are preserved (deep merge).
- Write tests injecting a mocked `.specweaver/dal_definitions.yaml` to ensure `load_settings()` effectively disables rule `S01` globally for `DAL_E`, but leaves it strictly enforced for `DAL_A`.
- Assert Pydantic instantly fails if `dal_definitions.yaml` contains an invalid enum like `warn_threshold: "apple"`.

### Pre-Commit Gate
- Architecture Validation runs successfully, ensuring `config/settings.py` strictly adheres to `consumes: []` (no circular imports from Validation).
- `pytest -m unit` reports PASSED.

## Session Handoff
Currently in COMPLETE state. All pre-commit quality gates have passed.
