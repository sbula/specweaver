# B-VAL-01 SF-02 — Flow Integration & CLI

**Status**: COMPLETED · **FRs owned**: FR-1, FR-5, FR-6 (recorded 2026-08-17 under `specweaver-dev`
§3.2c, from `INT-US-10-SF01-MIG`) · **Depends on**: SF-01 · Design:
[B-VAL-01_design.md](B-VAL-01_design.md) §Sub-features → SF-02

## Goal

Expose the SF-01 engine as `sw drift`. The `flow/` layer loads the plan, parses the target file, runs
`detect_drift`, and — with `--analyze` — asks an LLM for the root cause of each drift.

## Changes

**CLI**

1. [NEW] [drift.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/drift.py) in
   `src/specweaver/cli/` — sub-app `drift_app` on `_core.app`; implements
   `sw drift check <target_file> [--analyze] [--plan <plan_yaml>]`; runs the check with
   `PipelineDefinition.create_single_step` and `PipelineRunner`. Plan lookup through `LineageMixin`
   (`target_file` UUID → `PlanArtifact` parent, with its `Task` definitions) was the planned fallback
   without `--plan`; Q1 made `--plan` required instead.
2. [MODIFY] [\_\_init\_\_.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/__init__.py)
   — register the `drift` submodule with the other command groups.

**Flow**

3. [MODIFY] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/models.py) —
   add `StepAction.DETECT` (or ANALYZE) and `StepTarget.DRIFT`.
4. [NEW] [\_drift.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/_drift.py) —
   `DriftCheckHandler`: loads the baseline from the `PlanArtifact`, parses the target file, runs
   `drift_detector.detect_drift(file_ast, expected_signatures)`. **FR-5:** if
   `step.params.get("analyze")` is True, formats the findings into a prompt, calls the LLM through
   `context.llm`, and prints a human-readable root-cause analysis.
5. [MODIFY] [handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/handlers.py)
   — import `DriftCheckHandler` from `_drift.py`; map it to `(StepAction.DETECT, StepTarget.DRIFT)`
   in `StepHandlerRegistry`.

## Tests

| Tier | Case |
|---|---|
| Unit | mocked DB and Lineage: `DriftCheckHandler` formatting; LLM branch with `--analyze`; mocked AST failures → prompt syntax |
| Unit | FR-5 absence: no `--analyze` with an LLM attached → no LLM call (added later; without it the guard could be deleted with the suite green) |
| Integration | `pytest tests/integration/cli/test_cli_drift.py` (to be created) — command starts and formats results |
| E2E | un-skip the drift methods in `test_validation_pipeline_e2e.py` |

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | Lineage DB tracks parent/child UUIDs, not file paths. Auto-resolve would trace `Code UUID -> Spec UUID -> Plan UUID`, then scan `specs/*_plan.yaml` for the file with that `Plan UUID` — O(N). Acceptable for the NFRs? | **Add `--plan`**: `sw drift check <file> --plan <plan_yaml>`, as standard validation demands `--spec`. "This keeps it 100% fast, avoids globbing, and is explicit." |

Q1 is why the design deletes FR-2 (lineage baseline fetch); see the design.
