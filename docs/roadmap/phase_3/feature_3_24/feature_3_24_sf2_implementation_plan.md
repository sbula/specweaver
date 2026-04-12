# Implementation Plan: Automated iterative decomposition [SF-2: Verified Iterative Loop]
- **Feature ID**: 3_24
- **Sub-Feature**: SF-2 — Verified Iterative Loop & Traceability Enforcement
- **Design Document**: docs/roadmap/phase_3/feature_3_24/feature_3_24_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_24/feature_3_24_sf2_implementation_plan.md
- **Status**: COMPLETE

## Goal Description

Integrate the `fan_out()` orchestration capability into the core pipeline layer through a verified execution loop. This satisfies FR-2 (HITL presentation), FR-4 (Quality Automation loop limits), and FR-5 (Blast Radius Coverage assertion). 
To align strictly with the pipeline State Machine, we will split the operation into two distinct pipeline phases: `DECOMPOSE` (generation via LLM) and `ORCHESTRATE` (triggering sub-pipelines via `fan_out`). 
Furthermore, we will document the rigid DMZ coverage assertion logic prominently to ensure all future developers are aware of this specific validation boundary.

## Proposed Changes

### Flow Engine Core (`src/specweaver/flow/`)

#### [MODIFY] `src/specweaver/flow/models.py`
- Add `StepAction.ORCHESTRATE = "orchestrate"` to the `StepAction` Enum.
- Add `StepTarget.COMPONENTS = "components"` to the `StepTarget` Enum.
- Append `(StepAction.ORCHESTRATE, StepTarget.COMPONENTS)` to `VALID_STEP_COMBINATIONS`.

#### [NEW] `src/specweaver/flow/_decompose.py`
- Implements `DecomposeFeatureHandler(StepHandler)`:
    - Reads the `feature_spec.md` target.
    - Triggers the `FeatureDecomposer` (see Drafting Layer).
    - **Coverage Assertion (FR-5)**: Receives the `DecompositionPlan`. If the `coverage_score` is `< 1.0` or blast radius topologies don't align, returns `FAILED`. This triggers the pipeline's native 3-strike loop-back securely without invoking the HITL gate natively.
    - Saves the `DecompositionPlan` to an artifact/database and returns `PASSED` (which proceeds to the HITL Gate).
- Implements `OrchestrateComponentsHandler(StepHandler)`:
    - Reads the approved `DecompositionPlan`.
    - Generates `new_feature.yaml` (or equivalent component pipeline definitions) mapped to the `components` list.
    - Executes `self._runner.fan_out(sub_pipelines)`.
    - Returns `PASSED` if all sub-pipelines successfully hit `COMPLETED`, else `FAILED`.

#### [MODIFY] `src/specweaver/flow/handlers.py`
- Register `StepAction.DECOMPOSE` + `StepTarget.FEATURE` -> `DecomposeFeatureHandler()`.
- Register `StepAction.ORCHESTRATE` + `StepTarget.COMPONENTS` -> `OrchestrateComponentsHandler()`.

### Drafting Layer (`src/specweaver/drafting/`)

#### [NEW] `src/specweaver/drafting/decomposer.py`
- Implements `FeatureDecomposer`:
    - Given a target `feature_spec.md`, constructs an LLM prompt injecting the Blast Radius nodes and existing Topology.
    - Executes execution instructions for Structured Output formatting corresponding exactly to the Pydantic `DecompositionPlan`.
    - Native computation of `coverage_score` by comparing proposed components vs Blast Radius items explicitly.

### Pipeline Definitions (`src/specweaver/pipelines/`)

#### [MODIFY] `feature_decomposition.yaml`
- Update the `decompose` step to output the plan and await HITL approval natively.
- **[NEW]** Append the `orchestrate` step matching action `orchestrate` and target `components`.

### Documentation 

#### [MODIFY] `docs/dev_guides/pipeline_engine_guide.md`
- Provide a dedicated, prominent section heavily utilizing `> [!WARNING]` and `> [!CAUTION]` callouts detailing the **Blast Radius Coverage Mapping loop logic** inside `DecomposeFeatureHandler`.
- Ensure this section clearly dictates that modifying the pipeline bounds, or circumventing structured LLM coverage assertions, explicitly violates DMZ integrity requirements.

## Open Questions
- None. The dual-step architectural mapping satisfies HITL mechanics natively without blocking pipeline flow limits.

## Verification Plan

### Automated Tests
- **Unit**: Verify `DecomposeFeatureHandler` appropriately emits `RunStatus.FAILED` natively upon any `DecompositionPlan` where `coverage_score < 1.0`.
- **Unit**: Verify `OrchestrateComponentsHandler` successfully constructs exactly `N` sub-pipelines as matching the approved components list.
- **Integration**: Verify `feature_decomposition.yaml` successfully loops back upon draft failures within `test_feature_pipeline.py`.

### Manual Verification
- Execute `sw pipeline run feature_decomposition` to observe the HITL output prompt natively rendering the Decomposition JSON output, simulating approval, and triggering the underlying asynchronous pipeline log events for fan-out.
