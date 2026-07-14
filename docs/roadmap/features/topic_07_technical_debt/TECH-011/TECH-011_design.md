# Design: Load-Time Params Validation for All Pipeline Step Types

- **Feature ID**: TECH-011
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found during C-EXEC-02 SF-2's implementation-plan Phase 4 (2026-07-14), Q1.

## Problem Statement

`PipelineStep.params: dict[str, Any]` is opaque to `PipelineDefinition.validate_flow()` — no step type's `params` are validated at pipeline-load time. Each handler validates its own `params` only when the step actually **executes**, potentially much later in a long, HITL-gated pipeline run. Combined with Pydantic's default `extra="ignore"` on `PipelineStep` (a mistyped step-level key is silently dropped, not rejected), a simple author typo — e.g. `script:` at the step level instead of nested under `params:` — surfaces as a confusing runtime handler error instead of an immediate, clear pipeline-validation failure.

This is not new to C-EXEC-02's `action: bash` steps — it's true of every existing step type (`action: validate`'s `kind`/`coverage`, `action: generate`'s params, etc.). C-EXEC-02 SF-2 deliberately did **not** special-case bash-step params validation at load time (see its implementation plan's Q1) specifically to avoid introducing the first action-specific exception to this uniform-but-late-failing behavior — the real fix, if wanted, should apply to all step types uniformly, which is what this ticket is for.

## Goal

Give every pipeline step type fast, load-time feedback on malformed/missing `params`, consistent with how `PipelineDefinition.validate_flow()` already fails fast on invalid `(action, target)` combinations — without introducing per-action-type special cases scattered across the validation layer.

## Candidate Approaches (not yet designed)

1. **Per-action `params` schema registry** — each `StepAction` maps to a Pydantic model describing its expected `params` shape (e.g. `BashStepParams(script: str, args: list[str] = [], ...)`); `validate_flow()` looks up the schema by `step.action` and validates `step.params` against it, collecting errors the same way it already collects `(action, target)` combination errors.
2. **Per-handler `validate_params(params) -> list[str]` hook** — extend the `StepHandler` protocol with an optional classmethod/staticmethod handlers can implement for load-time checks, called by `validate_flow()` for every step whose action has a registered handler with that hook. Handlers without the hook are silently skipped (backward compatible, opt-in).
3. **Do nothing globally, keep it per-handler at runtime** — explicitly reject this ticket's premise; document the footgun instead. (The status quo — not a "do nothing" ticket by definition, but worth stating as the baseline being evaluated against.)

## Non-Goals (proposed, pending design)

- Retrofitting every existing step type's params validation in one PR — likely warrants its own phased sub-feature breakdown (start with a couple of the most typo-prone step types, expand from there).
- Changing `PipelineStep`'s `extra="ignore"` Pydantic config globally — that's a separate, more invasive decision with its own blast radius (could break existing pipeline YAMLs that rely on being tolerant of extra/legacy keys).

## Next Step

Run this through the `specweaver-design` skill properly (Research → Feature Detail → Decompose → Document → Consistency Check) before implementation — this stub only captures the problem statement and candidate approaches, not a reviewed design.
