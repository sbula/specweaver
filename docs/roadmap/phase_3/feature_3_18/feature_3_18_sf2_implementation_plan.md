# Implementation Plan: AST Drift Detection [SF-2: Flow Integration & CLI]
- **Feature ID**: 3.14a
- **Sub-Feature**: SF-2 — Flow Integration & CLI
- **Design Document**: docs/roadmap/phase_3/feature_3_18/feature_3_18_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_18/feature_3_18_sf2_implementation_plan.md
- **Status**: COMPLETED

## Goal Description
Expose the previously built AST Drift Engine (SF-1) through the SpecWeaver CLI via the `sw drift` command. It integrates the pure-logic `detect_drift` capabilities into the intelligent execution flow (`flow/` layer), fetching the necessary lineage UUIDs, locating the parent Spec/Plan, doing the check, and optionally invoking an LLM via `--analyze` to root-cause any detected AST drifts. 

## Proposed Changes

---

### CLI Layer
Create the CLI hook for developer interaction.

#### [NEW] [drift.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/drift.py)
Create `drift.py` inside `src/specweaver/cli/` to handle the `sw drift check` command.
- Will register a sub-app `drift_app` attached to `_core.app`.
- Implements `sw drift check <target_file> [--analyze] [--plan <plan_yaml>]`.
- Uses `PipelineDefinition.create_single_step` and `PipelineRunner` to execute the check seamlessly. 
- Discovers the Plan Artifact (and its `Task` definitions) by querying `LineageMixin` to map the `target_file`'s UUID to its `PlanArtifact` parent if `--plan` is not provided.

#### [MODIFY] [\_\_init\_\_.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/__init__.py)
Register the new `drift` submodule so it matches other command groupings.

---

### Flow Execution Layer
Bind the logic to the pipeline runner syntax.

#### [MODIFY] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/models.py)
Extend `StepAction` and `StepTarget` Enums.
- Add `StepAction.DETECT` (or ANALYZE) 
- Add `StepTarget.DRIFT`

#### [NEW] [\_drift.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/_drift.py)
Implementation of the `DriftCheckHandler`.
- Resolves the baseline constraints from the `PlanArtifact`. (via `--plan` or DB fallback).
- Reads the AST of the target file.
- Executes `drift_detector.detect_drift(file_ast, expected_signatures)`.
- **LLM Extension (FR-5)**: If `step.params.get("analyze")` is True, formats the structural failures into a prompt, invokes the LLM through `context.llm`, and outputs a Human-Readable Root-Cause Analysis.

#### [MODIFY] [handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/handlers.py)
- Import `DriftCheckHandler` from `_drift.py` and map it to `(StepAction.DETECT, StepTarget.DRIFT)` in `StepHandlerRegistry`.

## Open Questions

> [!WARNING]
> **Plan Resolution Constraints**
> Lineage DB tracks artifact parent/child UUIDs, but not exact file paths. To resolve a Plan for a target code file automatically (without demanding a `--plan` CLI flag), the Flow handler will trace `Code UUID` -> `Spec UUID` -> `Plan UUID`. It will then scan `specs/*_plan.yaml` to find the file matching `Plan UUID`. Is this file scan O(N) acceptable for our NFRs? 
> **Recommendation**: Since standard validation demands `--spec`, we should just add `--plan` to `sw drift check <file> --plan <plan_yaml>`. This keeps it 100% fast, avoids globbing, and is explicit. Do you approve adding `--plan`?

## Verification Plan

### Automated Tests
- **Unit**: Mock DB and Lineage calls, verify `DriftCheckHandler` formatting and LLM branch coverage when `--analyze` is flagged. Mock AST failures to verify prompt syntax. 
- **Integration**: `pytest tests/integration/cli/test_cli_drift.py` (to be created) verifying CLI command spins up and formats results properly.
- **E2E**: Un-skip the `test_validation_pipeline_e2e.py` drift methods now that SF-2 Flow hooks are cleanly integrated.
