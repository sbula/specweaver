# Implementation Plan: Rubrics-as-Content Validation [Phase 6 corrections]
- **Feature ID**: C-VAL-05
- **Design Document**: docs/roadmap/features/topic_05_validation/C-VAL-05/C-VAL-05_design.md
- **Design Section**: §Corrections (Phase 6, 2026-10-17)
- **Implementation Plan**: docs/roadmap/features/topic_05_validation/C-VAL-05/C-VAL-05_corrections_plan.md
- **Status**: APPROVED by the user 2026-10-17 · built: CB-1 `be9b8f9b`, CB-2 `38bc1a41`, CB-3

**Owns**: K-1 (NFR-2), K-2 (FR-4), K-3 (FR-1, FR-3 mutants)

## Shape

| Piece | Where | Tag |
|---|---|---|
| `_candidates`: project variant, project plain, shipped variant, shipped plain | `assurance/validation/rubrics/loader.py:46-60` | MODIFY |
| the review prompt builder hands back the loaded `Rubric` with the instructions; the spec and code review steps put `rubric: {id, version, checksum, source}` (source as text) in their result's output | `core/flow/handlers/review.py` (`resolve_review_instructions`, `_build_review_prompt`, the two step results) | MODIFY |
| mutants for the DAL variant and the raise, and for K-1, K-2 | `C-VAL-05_mutants.json` | MODIFY |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the search order | NFR-2 | a DAL-A project with its own plain `spec_review.md` is judged by the shipped DAL-A file — red today |
| CB-2 | the rubric in the step result | FR-4 | a review run's result has no `rubric` — red today |
| CB-3 | the two missing mutants | FR-1, FR-3 | each must be killed by the existing tests; a survivor gets its test first |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit | `load_rubric` with a project plain rubric at DAL-A, and the control: a project DAL-A rubric still wins over its own plain one |
| CB-2 | integration + e2e | `ReviewSpecHandler` with a recording adapter: the result names the rubric; `sw review` saves it in the run state |

## Research Notes

- `_candidates` builds all variants first, then all plain files (`loader.py:46-60`); the comment states
  the opposite of the order.
- `resolve_review_instructions` loads the rubric and only logs it (`review.py:109-132`); the step result
  is built at `review.py:442`.
- The existing e2e `test_project_rubric_reaches_the_reviewer_e2e.py` runs `ReviewSpecHandler` with a
  recording adapter — the model for CB-2's test.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| — | none open: Q1–Q3 settled in the design `[agreed 2026-10-17]` | — |

## Backlog

none
