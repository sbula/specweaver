# Design: Load-Time Params Validation for All Pipeline Step Types

- **Feature ID**: TECH-011
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-19
- **Origin**: Found during C-EXEC-02 SF-02's implementation-plan Phase 4 (2026-07-14), Q1.

## Problem Statement

`PipelineStep.params: dict[str, Any]` is opaque to `PipelineDefinition.validate_flow()` — no step
type's `params` are validated at pipeline-load time. Each handler validates its own `params` only
when the step actually **executes**, potentially much later in a long, HITL-gated pipeline run.
Combined with Pydantic's default `extra="ignore"` on `PipelineStep` (a mistyped step-level key is
silently dropped, not rejected), a simple author typo — e.g. `script:` at the step level instead of
nested under `params:` — surfaces as a confusing runtime handler error instead of an immediate,
clear pipeline-validation failure.

This is not new to C-EXEC-02's `action: bash` steps — it's true of every existing step type
(`action: validate`'s `kind`/`coverage`, `action: generate`'s params, etc.). C-EXEC-02 SF-02
deliberately did **not** special-case bash-step params validation at load time (see its
implementation plan's Q1) specifically to avoid introducing the first action-specific exception to
this uniform-but-late-failing behavior — the real fix, if wanted, should apply to all step types
uniformly, which is what this ticket is for.

## Goal

Give every pipeline step type fast, load-time feedback on malformed/missing `params`, consistent
with how `PipelineDefinition.validate_flow()` already fails fast on invalid `(action, target)`
combinations — without introducing per-action-type special cases scattered across the validation
layer.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Required params are checked at load | `validate_flow()` | looks up what each step's action requires and reports what is absent | an author learns at load, not after the earlier steps of a gated run have already executed |
| FR-2 | A misplaced key is named, not just missed | `validate_flow()` | sees a required param sitting at step level and says where it belongs | the ticket's own example — `script:` beside `action:` — reports *"it belongs under 'params:'"* instead of *"missing param"* about a value that is right there |

## The decision that changed on contact

Approach 2 as filed, plus a correction the filing could not have known.

`extra="forbid"` is the obvious reading of *"a mistyped step-level key is silently dropped, not
rejected"*, and it is wrong here. This repo states a **forward-compatibility contract** outright, in
`test_load_with_extra_fields_ignored`: an unknown field from a future version must still load.
Forbidding extras reverses a deliberate decision, and measured, it broke 11 of 16 shipped pipelines.

`extra="allow"` keeps both properties. An unknown field loads, and it is still *there* when
`validate_flow()` runs — which is what lets a misplaced param be named without forbidding fields
nobody has invented yet.

**One real field was hiding in the extras.** `rule` is used by every validation pipeline and was
never declared, absorbed by `extra="ignore"` along with the typos. It is declared now, which is
what made the model able to tell a field from a mistake at all.

**The registry is a mechanism, not a demand.** Every action is looked up; one that declares nothing
passes. `C-EXEC-02` refused to special-case bash to avoid the first action-specific exception, and
that holds: bash is the only action with a requirement today because it is the only one that names
one, and adding another is one line.

## Verifiable Proof

| FR | Test |
|---|---|
| FR-1 | `tests/unit/core/flow/engine/test_step_params_validated_at_load.py` — removing the call, or emptying the registry, each fail 3 |
| FR-2 | the same file — dropping the misplacement branch fails 1, and reverting to `extra="ignore"` fails 1, because the key vanishes before anything can see it |

## Live demo

`sw run` of a pipeline whose bash step has `script:` beside `params:` stops before any step runs
and says it belongs under `params:`; one with no `script` at all says it is missing.
`tests/e2e/capabilities/sandbox/test_bash_step_journey_e2e.py` does exactly this.
