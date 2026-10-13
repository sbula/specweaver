# E-INTL-03 — Spec Review Engine

**Status**: ✅ Finished — signed off by the user 2026-10-13. · **Phase**: 1 (Step 4)

| | |
|---|---|
| Touches | `workflows/review/` (reviewer, `sw review`) · `core/flow/handlers/review.py` |
| Uses | `E-INTL-01` (the model, masking) · `C-VAL-05` (the criteria) · `E-SENS-01` (read tools) |
| Plan | [as built](E-INTL-03_implementation_plan.md) |

## What it does

`sw review <spec>` has a model judge a spec on meaning; `sw review <code> --spec <spec>` judges
code against its spec. The model gets the rubric's criteria and a fixed output contract, and
answers with a verdict line, findings and a summary.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Spec review | `sw review <spec>` | SHALL send the spec with the rubric's criteria and the output contract, and print the verdict, summary and findings | a spec is judged on meaning |
| FR-2 | Code review | `sw review <code> --spec <spec>` | SHALL send the spec and the code, and print the same | code is judged against its spec |
| FR-3 | Verdict | Reviewer | SHALL take the verdict from the first verdict line only; no line is DENIED; a failed model call is ERROR; DENIED and ERROR exit 1 | a denial is never read as acceptance |
| FR-4 | Tools | Reviewer | SHALL give the model the read tools when its adapter supports them, and add the files it mentions between tool rounds, masked (`E-INTL-01` FR-3) | the model can look things up instead of guessing |

## Live demo

Against real Gemini: `sw review greeter_spec.md` and `sw review src/greeter.py --spec
greeter_spec.md` each come back with `VERDICT: ACCEPTED` or `VERDICT: DENIED` and its findings; a
code review's request holds both files. The nightly live run (`scripts/live.py`) checks both.
