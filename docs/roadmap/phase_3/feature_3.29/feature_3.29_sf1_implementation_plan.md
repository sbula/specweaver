# Implementation Plan: Archetype-Based Rule Sets [SF-1: Injection & Orchestrator]
- **Feature ID**: 3.29
- **Sub-Feature**: SF-1 — Injection & Orchestrator
- **Design Document**: docs/roadmap/phase_3/feature_3.29/feature_3.29_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.29/feature_3.29_sf1_implementation_plan.md
- **Status**: APPROVED

## 1. Summary
This implementation plan covers SF-1: wiring the `flow` Orchestrator to natively read the target component's `archetype`, dynamically overlaying the validation YAML, and injecting the memory-safe AST payload down into the Validation DMZ without violating the strict `forbids: loom/*` boundary.

## 2. Dependencies
- **Depends On**: None. This is the first Sub-Feature.
- **Transitive Assumptions**: `tree_sitter` dependencies natively function correctly. `CodeStructureAtom` cleanly returns purely serialized python `dict` outputs without leaking OS/C-pointer memory locks.

## 3. Functional Requirements Covered
- **FR-1 Profile Orchestration:** `PipelineRunner` dynamically parses `context.yaml` archetype to resolve the correct YAML pipeline extensions.

## 4. File Modifications

### 4.1. [NEW] `src/specweaver/core/config/archetype_resolver.py`
- **Purpose**: Creates an `ArchetypeResolver` (modeling the battle-tested `DALResolver`) that securely parses an execution target path upward, finding the closest `context.yaml` and extracting the `archetype` string (e.g., `spring-boot`, `vue`).
- **Signatures**:
  ```python
  class ArchetypeResolver:
      def __init__(self, workspace_root: Path):
          ...
      def resolve(self, target_path: Path) -> str | None:
          ...
  ```

### 4.2. [MODIFY] `src/specweaver/core/flow/_validation.py`
- **Purpose**: Upgrade the `ValidateSpecHandler` and `ValidateCodeHandler` to dynamically load context bounds and execute the payload injection without importing native logic.
- **Changes**:
  1. Instantiate the new `ArchetypeResolver` during `_resolve_merged_settings` (or natively before `_run_validation`).
  2. Modify `_run_validation` in `ValidateCodeHandler`:
     - Run `CodeStructureAtom(cwd).run({"intent": "extract_skeleton", "path": code_path})` to fetch the AST Dictionary.
     - Change pipeline loading logic: Try `pipeline_name = f"validation_code_{archetype}"`. Fallback to `"validation_code_default"`.
     - Inject the payload dictionary using parameter injection (Option B approved). Loop over `pipeline.steps` and assign `step.params["ast_payload"] = payload` so the Rules instantiate correctly.
  3. Modify `_run_validation` in `ValidateSpecHandler`:
     - Apply exact same dynamic archetype template fallback logic (loading `validation_spec_{archetype}.yaml`).

## 5. Architectural Consistency
- **DMZ Integrity**: The `flow` application correctly acts as the side-effect broker. It extracts the AST via Loom and sends it purely as a Dictionary to `assurance/`, permanently solving the layer violation.
- **Rule Flexibility**: By using `step.params["ast_payload"]` at runtime, we preserve the `Rule.check(spec_text)` abstraction perfectly without shattering global rules.

## 6. Backlog / Deferred Maintenance
- **Refactoring Task [Option A]**: Moving forward, SpecWeaver should unify Dependency Injection across the engine. A dedicated engineering ticket must be opened to refactor `Rule.check()` recursively across the 30+ validation rules to formally support an explicitly typed `injected_payload: dict[str, Any] | None = None` argument. For this feature, the localized `__init__` parameter manipulation successfully stabilizes the bounds.

## 7. Verification Steps
- [x] **Unit Testing**: Created `tests/unit/core/config/test_archetype_resolver.py` proving recursive path fallback finding the nearest `archetype` metadata string. Including edge cases for missing and malformed YAML.
- [x] **Integration Testing**: Created an integration test executing `ValidateCodeHandler` and verifying `CodeStructureAtom` intercepts the file successfully and injects the resulting `dict` into `step.params` without failing execution. All unit tests, integration tests, and E2E tests are green.

## 8. Implementation Notes (Deviations)
- `CodeStructureAtom` required passing `cwd` manually (similarly to `QARunnerAtom`). Modified the Atom to construct its own `FileExecutor` avoiding a Domain Dependency architecture violation inside `flow/`.
