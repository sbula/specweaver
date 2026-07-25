# Pipeline Engine

## Step Model

A pipeline is a sequence of **steps**. Each step combines:
- **Action** (verb): `draft`, `validate`, `review`, `generate`, `lint_fix`, `plan`, `decompose`, `arbitrate`
- **Target** (noun): `spec`, `code`, `tests`, `feature`, `verdict`

```yaml
# Example: new_feature.yaml
steps:
  - name: validate_spec
    action: validate
    target: spec
    gate:
      type: auto
      condition: all_passed
      on_fail: abort
```

## Gate Model

Gates sit after steps and control flow. Each gate has:
- **type**: `auto` (machine-evaluated) or `hitl` (human approves)
- **condition**: `all_passed`, `accepted`, `completed`
- **on_fail**: `abort`, `retry`, `loop_back`, `continue`
- **loop_target**: step name to jump back to (for `loop_back`)
- **max_retries**: bounded retry/loop count

```text
               ┌─────────┐
  Step result ─▶  Gate    ├──pass──▶ Next step
               └────┬────┘
                    │fail
           ┌────────┼────────┐
         abort    retry   loop_back
          │         │        │
        STOP    re-run    jump to
                 step    earlier step
```

## Handler Registry

The `StepHandlerRegistry` maps `(action, target)` pairs to handler classes:

| Action + Target | Handler | Module |
|----------------|---------|--------|
| `draft+spec` | `DraftSpecHandler` | `core/flow/handlers/draft.py` |
| `draft+feature` | `DraftFeatureHandler` | `core/flow/handlers/draft.py` |
| `validate+spec` | `ValidateSpecHandler` | `core/flow/handlers/validation.py` |
| `validate+feature` | `ValidateSpecHandler` (routes `kind=feature` → `validation_spec_feature`) | `core/flow/handlers/validation.py` |
| `validate+code` | `ValidateCodeHandler` | `core/flow/handlers/validation.py` |
| `validate+tests` | `ValidateTestsHandler` | `core/flow/handlers/validation.py` |
| `review+spec` | `ReviewSpecHandler` | `core/flow/handlers/review.py` |
| `review+code` | `ReviewCodeHandler` | `core/flow/handlers/review.py` |
| `generate+code` | `GenerateCodeHandler` | `core/flow/handlers/generation.py` |
| `generate+tests` | `GenerateTestsHandler` | `core/flow/handlers/generation.py` |
| `generate+contract` | `GenerateContractHandler` | `core/flow/handlers/generation.py` |
| `generate+scenario` | `GenerateScenarioHandler` | `core/flow/handlers/scenario.py` |
| `convert+scenario` | `ConvertScenarioHandler` | `core/flow/handlers/scenario.py` |
| `lint_fix+code` | `LintFixHandler` | `core/flow/handlers/lint_fix.py` |
| `plan+spec` | `PlanSpecHandler` | `core/flow/handlers/generation.py` |
| `enrich+standards` | `EnrichStandardsHandler` | `core/flow/handlers/standards.py` |
| `detect+drift` | `DriftCheckHandler` | `core/flow/handlers/drift.py` |
| `decompose+feature` | `DecomposeFeatureHandler` | `core/flow/handlers/decompose.py` |
| `orchestrate+components` | `OrchestrateComponentsHandler` | `core/flow/handlers/decompose.py` |
| `arbitrate+verdict` | `ArbitrateVerdictHandler` | `core/flow/handlers/arbiter.py` |
| `bash+script` | `BashActionHandler` | `core/flow/handlers/bash_action.py` |

> Source of truth: `StepHandlerRegistry.__init__` in `core/flow/handlers/registry.py`. A pair
> present in `VALID_STEP_COMBINATIONS` (`engine/models.py`) but absent here makes the pipeline
> unrunnable — the runner errors with "No handler registered for `<action>`+`<target>`" at that
> step. That was exactly the `feature_decomposition` defect INT-US-21 FR-1 closed.

## Runner

The `PipelineRunner` walks through steps sequentially:
1. Look up handler in registry
2. Execute handler → get `StepResult`
3. If step has a gate → evaluate it (advance/stop/retry/loop_back/park)
4. Persist state to SQLite after each step (supports resume)
5. Emit events for UI progress display

State is persisted so interrupted runs can `resume(run_id)`.
