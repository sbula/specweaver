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
4. **Hydrate plan context** from the step's output (see below)
5. Persist state to SQLite after each step (supports resume)
6. Emit events for UI progress display

State is persisted so interrupted runs can `resume(run_id)`.

### Plan Context Hydration (`engine/hydration.py`)

Two distinct plan concepts flow between steps, on **two distinct `RunContext` fields**
(INT-US-21 AD-1 — they previously shared one field that nothing ever wrote):

| Producing step | Field | Content | Consumed by |
|---|---|---|---|
| `decompose+feature` | `context.decomposition` | `DecompositionPlan` as canonical JSON | `OrchestrateComponentsHandler` |
| `plan+spec` | `context.plan` | implementation `PlanArtifact` file body | `GenerateCode/TestsHandler` (`add_plan`) |

`hydrate_plan_context()` is the single writer for both. Contract:

- **Only `PASSED` results hydrate.** A non-`PASSED` result *clears* the field that step owns, so a
  superseded plan can never survive a failed re-run and be silently consumed downstream.
- **Never raises.** A missing key, deleted file, unreadable path or non-serializable output
  degrades to a WARNING and leaves the field untouched, so the consuming step fails with its own
  specific message.
- **Serializes with `default=str`, matching `StateStore` exactly** (`engine/store.py`). This is
  load-bearing: without it an output carrying a `Path`/`set` would fail to hydrate on the live path
  but succeed after a resume, making the same run behave differently depending on whether it was
  interrupted.

> [!IMPORTANT]
> The hook is called from the **join point both advance paths reach** — after the gate's `advance`
> fall-through *and* after the no-gate branch. Placing it inside the gate block would silently skip
> every gateless plan/decompose step.

> [!CAUTION]
> `RunContext` is **shared** across concurrent fan-out sub-runners
> (`handlers/decompose.py`), and the runner writes `run_id`/`step_records` onto it every step.
> Concurrent sub-runs therefore race on this state — tracked as **`TECH-009`**.
