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
| `draft+spec` | `DraftSpecHandler` | `flow/_draft.py` |
| `validate+spec` | `ValidateSpecHandler` | `flow/_validation.py` |
| `validate+code` | `ValidateCodeHandler` | `flow/_validation.py` |
| `validate+tests` | `ValidateTestsHandler` | `flow/_validation.py` |
| `review+spec` | `ReviewSpecHandler` | `flow/_review.py` |
| `review+code` | `ReviewCodeHandler` | `flow/_review.py` |
| `generate+code` | `GenerateCodeHandler` | `flow/_generation.py` |
| `generate+tests` | `GenerateTestsHandler` | `flow/_generation.py` |
| `lint_fix+code` | `LintFixHandler` | `flow/_lint_fix.py` |
| `plan+spec` | `PlanSpecHandler` | `flow/_generation.py` |
| `arbitrate+verdict` | `ArbitrateVerdictHandler` | `flow/_arbiter.py` |

## Runner

The `PipelineRunner` walks through steps sequentially:
1. Look up handler in registry
2. Execute handler → get `StepResult`
3. If step has a gate → evaluate it (advance/stop/retry/loop_back/park)
4. Persist state to SQLite after each step (supports resume)
5. Emit events for UI progress display

State is persisted so interrupted runs can `resume(run_id)`.
