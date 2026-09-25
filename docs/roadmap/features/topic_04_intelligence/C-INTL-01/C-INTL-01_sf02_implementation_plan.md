# C-INTL-01 SF-02 — Verified Iterative Loop & Traceability Enforcement

**Status**: COMPLETE · **FRs owned**: FR-2 (HITL presentation), FR-4 (quality loop limits), FR-5
(Blast Radius coverage assertion) · **Depends on**: SF-01 · Design:
[C-INTL-01_design.md](C-INTL-01_design.md) §Sub-features → SF-02

## Goal

Put `fan_out()` into the pipeline behind a verified loop. To fit the pipeline state machine, the work
is two steps: `DECOMPOSE` (LLM generation) and `ORCHESTRATE` (sub-pipelines via `fan_out`). The DMZ
coverage assertion is documented prominently for future developers.

## Changes

**Flow engine** (`src/specweaver/flow/`)

1. `src/specweaver/flow/models.py` [MODIFY] — `StepAction.ORCHESTRATE = "orchestrate"`,
   `StepTarget.COMPONENTS = "components"`; add `(StepAction.ORCHESTRATE, StepTarget.COMPONENTS)` to
   `VALID_STEP_COMBINATIONS`.
2. `src/specweaver/flow/_decompose.py` [NEW]:
   - `DecomposeFeatureHandler(StepHandler)` — reads the `feature_spec.md` target; runs
     `FeatureDecomposer`. **FR-5:** if the `DecompositionPlan`'s `coverage_score` is `< 1.0` or blast
     radius topologies don't align, returns `FAILED` — the pipeline's 3-strike loop-back runs, the
     HITL gate does not. Otherwise saves the plan (artifact/database) and returns `PASSED`, which
     leads to the HITL gate.
   - `OrchestrateComponentsHandler(StepHandler)` — reads the approved `DecompositionPlan`; builds
     `new_feature.yaml` (or equivalent component pipeline definitions) per entry of `components`;
     runs `self._runner.fan_out(sub_pipelines)`; `PASSED` if every sub-pipeline reaches `COMPLETED`,
     else `FAILED`.
3. `src/specweaver/flow/handlers.py` [MODIFY] — register `StepAction.DECOMPOSE` + `StepTarget.FEATURE`
   -> `DecomposeFeatureHandler()` and `StepAction.ORCHESTRATE` + `StepTarget.COMPONENTS` ->
   `OrchestrateComponentsHandler()`.

**Drafting layer** (`src/specweaver/drafting/`)

4. `src/specweaver/drafting/decomposer.py` [NEW] — `FeatureDecomposer`: for a `feature_spec.md`,
   builds an LLM prompt with the Blast Radius nodes and existing Topology; requests Structured Output
   matching the Pydantic `DecompositionPlan`; computes `coverage_score` by comparing proposed
   components with the Blast Radius items.

**Pipelines** (`src/specweaver/pipelines/`)

5. `feature_decomposition.yaml` [MODIFY] — the `decompose` step outputs the plan and waits for HITL
   approval; **[NEW]** `orchestrate` step (action `orchestrate`, target `components`).

**Docs**

6. `docs/dev_guides/pipeline_engine_guide.md` [MODIFY] — a prominent section, with `> [!WARNING]` and
   `> [!CAUTION]` callouts, on the **Blast Radius Coverage Mapping loop logic** in
   `DecomposeFeatureHandler`: changing the pipeline bounds or bypassing the structured coverage
   assertion violates DMZ integrity.

No open questions: the two-step split gives HITL without blocking the pipeline.

## Tests

| Tier | Case |
|---|---|
| Unit | `DecomposeFeatureHandler` returns `RunStatus.FAILED` for any `DecompositionPlan` with `coverage_score < 1.0` |
| Unit | `OrchestrateComponentsHandler` builds exactly `N` sub-pipelines, one per approved component |
| Integration | `feature_decomposition.yaml` loops back on draft failures (`test_feature_pipeline.py`) |
| Manual | `sw pipeline run feature_decomposition` — HITL prompt shows the Decomposition JSON; approval triggers the async fan-out log events |

## As built

**Since moved** (checked 2026-09-25): handlers in `src/specweaver/core/flow/handlers/decompose.py`;
`FeatureDecomposer` in `src/specweaver/workflows/planning/decomposer.py`.
