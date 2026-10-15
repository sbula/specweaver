# Implementation Plan: Scenario Testing [SF-H: Spec conflicts and the kept suite]
- **Feature ID**: B-FLOW-01
- **Sub-Feature**: SF-H — Spec conflicts and the kept suite
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-01/B-FLOW-01_design.md
- **Design Section**: §Sub-features → SF-H
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-01/B-FLOW-01_sfh_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-15

**FRs owned**: FR-19, FR-20 · **Depends on**: SF-D (committed); uses SF-G's review record

## Goal

A spec that contradicts another spec or a contract is caught at review, before any code or
scenario exists. A scenario set that passed stays in the store and keeps checking its spec: a
later change cannot quietly break a requirement only it checked, and no coder sees the result.

## Shape

| Piece | Where | Tag |
|---|---|---|
| the review prompt gets a map of every other spec: path, title, purpose sentence, requirement ids and titles; the main conflict finder is the reviewer, which reads those specs, the contracts and the code with its file tools | `core/flow/handlers/spec_map.py` (NEW), `core/flow/handlers/review.py` | NEW / MODIFY |
| a sixth criterion: consistency with the project's other specs, contracts and code; each conflict a `- CONFLICT:` finding quoting both texts and naming both files | `assurance/validation/rubrics/spec_review.md` | MODIFY |
| one small certain signal beside it: a `## Contract` method declared with a different signature in another spec or a `contracts/` file is a named conflict | `spec_map.py` | NEW |
| any `CONFLICT:` finding, from the model or the check, makes the verdict DENIED, whatever the model's verdict line says | `core/flow/handlers/review.py` | MODIFY |
| after a passing dual run, the set is kept: `<store>/kept/<stem>.json` holds the spec's and the contract's SHA-256 | `core/flow/handlers/arbiter.py` (the no-failures path), `reviewed_spec.py` | MODIFY |
| a dual run with a fresh kept set does not run the scenario side on round 1; a changed spec or contract runs it, with the earlier set in its prompt | `core/flow/handlers/dual_pipeline.py` (`_sides_to_run`) | MODIFY |
| the acceptance step: every fresh kept set, run in a container against the current code; a report for the person, never a failure, never feedback (see Q2) | `core/flow/handlers/validation.py` (`kind: acceptance`), pipelines | MODIFY |
| the coding side of a dual run drops the acceptance step | `dual_pipeline.py` (`_SPEC_STEPS` → the steps the coder does not run) | MODIFY |
| the end of `sw run` shows the acceptance report: passed, failed per requirement, stale sets | `core/flow/interfaces/run_summary.py` | MODIFY |

> [!CAUTION]
> The acceptance step must never reach a coder. It returns PASSED with its report in the output,
> so the handover — which keeps only failed steps' errors — holds nothing of it; it writes nothing
> to `context.feedback`; and the coding side of a dual run does not run it.

> [!CAUTION]
> A model can invent a conflict. A `CONFLICT:` finding counts only when the file it names exists and
> the text it quotes is found in that file; otherwise it stays a warning in the report and does not
> deny. A wrong DENIED would block every dual run on that spec.

> [!NOTE]
> A kept set whose spec was deleted, or whose contract file is gone, is stale: the acceptance step
> lists it as stale and does not run it. The map reads `specs/**/*.md` without the spec under
> review; `sw implement` gets the acceptance step after `validate_code`.

> [!WARNING]
> The map grows with the number of specs and no prompt has a size budget. In a large project the
> map gets long; that is where `B-FLOW-04` retrieval is needed. The seam is recorded in its
> roadmap entry (`topic_03_flow_engine.md`), so no second, private retrieval is built here.

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the spec map in the review prompt; the sixth criterion; the signature check; DENIED on a conflict | FR-20 | a review whose model names a conflict between two specs still passes, and the prompt holds no other spec — red today |
| CB-2 | the kept record; reuse on an unchanged spec; regeneration on a change | FR-19 | a second dual run on an unchanged spec generates the scenarios again — red today |
| CB-3 | the acceptance step and its report | FR-19 | a change that breaks a kept scenario passes a normal run with no word to the person — red today |

| CB | Tier | Test |
|---|---|---|
| CB-1 | integration + e2e | the real review step over a real project with two specs that disagree on behaviour (not on a signature); the scripted model reads the other spec with its file tool and names the conflict; `sw review` in the e2e reports DENIED with both quotes |
| CB-2 | integration + e2e | the real dual handler and arbiter over the real store; the e2e runs twice and the second run makes no scenario call |
| CB-3 | integration + e2e | the real acceptance step in a container; the e2e breaks the code after a passing dual run, runs a normal pipeline, and `sw run` shows the failed requirement |

## Mutants

| id | Line neutralised | Must kill |
|---|---|---|
| `map-not-sent` | the spec map block in the review prompt | CB-1 |
| `signature-conflict-missed` | the signature comparison | CB-1 |
| `conflict-accepted` | the verdict on a conflict | CB-1 |
| `invented-conflict-denies` | the check that the quoted text is in the named file | CB-1 |
| `set-not-kept` | the kept-record write | CB-2 |
| `kept-set-regenerated` | the reuse of a fresh kept set | CB-2 |
| `changed-spec-reused` | the fingerprint comparison | CB-2 |
| `acceptance-feeds-back` | the acceptance step's status (PASSED → FAILED) | CB-3 |
| `stale-set-run` | the fresh-only filter | CB-3 |

## Research Notes

- The review prompt: `_build_review_prompt` adds skeleton context, the rubric and topology;
  `Reviewer.review_spec` adds the spec at priority 1 (`core/flow/handlers/review.py:140`,
  `workflows/review/reviewer.py:126`).
- No prompt anywhere gets a `TokenBudget` (`PromptBuilder(...)` in `prompting.py:52` passes none),
  so a block added to the review prompt is never truncated: pasting every other spec has no bound.
- The reviewer already gets READ file tools over the project when its model supports tools
  (`_build_tool_dispatcher(context, role="reviewer")`).
- `extract_methods` and `contract_names` (SF-F) parse a spec's `## Contract`; signatures are kept
  per method.
- The handover keeps only FAILED/ERROR steps' error messages and `files_touched`
  (`core/flow/engine/handover.py _failed_step_errors`).
- The arbiter's no-failures path returns PASSED with `verdict: no_failures`.
- `E-INTL-03` (finished) owns the spec review; FR-20 adds its conflict check as a B-FLOW-01 seam,
  noted in FR-20's row. `A-INTL-01` (planned) attacks contradictions inside one spec during
  drafting; FR-20 compares a spec with the others — they do not overlap.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | What a named conflict does to the review verdict | DENIED, so no review record is written and a dual run refuses the spec `[agreed 2026-10-15]` |
| Q2 | Where the acceptance step runs | at the end of `new_feature` and `sw implement`, in a container, a report at the end of `sw run`, never stopping the run `[agreed 2026-10-15]` |
| Q3 | How the review sees the other specs | a map of every other spec in the prompt, and the reviewer reads specs, contracts and code with its file tools; when `B-FLOW-04` ships, a "find related specs and code" tool joins them, suggesting only (`ADR-006`) `[agreed 2026-10-15]` |

> [!NOTE]
> Retrieval can cover specs: the built chunker cuts a spec into named sections
> ([check](../../../../analysis/specs_in_rag_plausibility_2026-10-15.md)); `B-FLOW-04` now names
> specs `[agreed 2026-10-15]`.

## Backlog

none
