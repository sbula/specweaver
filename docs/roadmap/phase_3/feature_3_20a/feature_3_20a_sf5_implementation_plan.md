# Implementation Plan: Feature 3.20a [SF-5: Legacy Linter Subsumption]
- **Feature ID**: 3.20a
- **Sub-Feature**: SF-5 — Legacy Linter Subsumption
- **Design Document**: docs/roadmap/phase_3/feature_3_20a/feature_3_20a_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-5
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_20a/feature_3_20a_sf5_implementation_plan.md
- **Status**: APPROVED

## 1. Description
This implementation plan covers the complete integration and adoption of `Tach` for SpecWeaver internal testing handling. The goal is to fully deprecate and remove overlapping internal Python architectural tests and custom deprecation logic scripts. 
(*Note: Global PEP-420 `__init__.py` deletion was spun out into SF-6 to isolate blast radius*).

---

## 2. Deep Analysis & Architectural Targets

### 2.1 Deprecation Subsumption
`tests/unit/validation/test_runner_removals.py` manually asserts `ImportError` on legacy APIs.
**Action:** Remove the manual testing. Ensure `src.specweaver.assurance.validation` is registered in `tach.toml` `interfaces`, expressly omitting `runner` from exports to enforce CI-level bounding instead of file-level crashes.

### 2.2 Boilerplate Verification Subsumption
`tests/unit/test_architecture.py` contains script logic asserting that `src.specweaver.interfaces.api` is not mapped incorrectly.
**Action:** Purge manual `.toml` Python parsing (`test_core_layers_never_depend_on_presentation`). Tach is now the authoritative rules engine, and PR governance oversees the TOML, preventing duplicate architectural testing effort.

---

## 3. Implementation Steps

1. [x] **Delete Testing Files**: Hard delete `tests/unit/validation/test_runner_removals.py`.
2. [x] **Strip Boilerplate**: Remove `test_tach_toml_enforces_resource_layer_modules` and `test_core_layers_never_depend_on_presentation` from `tests/unit/test_architecture.py`.
3. [x] **Register `validation` Interface**: Update `tach.toml` to explicitly map `src.specweaver.assurance.validation` into `modules` and `interfaces`, purposely excluding `runner` to formalize the CI deprecation block globally.

*Implementation Note: Also implemented a targeted integration test `test_tach_keeps_runner_soft_deprecated` to ensure `runner` is never accidentally re-added to `tach.toml`, and fixed bugs in `test_architecture.py` regarding `tach.toml` structure parsing which revealed and fixed several phantom/dead module exposures.*

---

## 4. Rollback Plan
If `tach` strict checks fail unexpectedly after linking the Validation subsystem boundaries, run standard Git rollback on the modifications.

---

## 5. Backlog / Deferred
- **[SF-6]**: Global Implicit Namespace conversion (deletion of all remaining 20 `__init__.py` files) and enforcing `strict = true` globally for all boundaries.
