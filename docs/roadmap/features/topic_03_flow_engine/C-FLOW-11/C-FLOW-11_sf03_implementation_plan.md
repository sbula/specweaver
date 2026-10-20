# Implementation Plan: Graduated Autonomy [SF-03: `sw implement` follows the dial]
- **Feature ID**: C-FLOW-11
- **Sub-Feature**: SF-03 — `sw implement` follows the dial
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-11/C-FLOW-11_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-11/C-FLOW-11_sf03_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-20

**FRs owned**: FR-10 · **NFRs**: NFR-1 · **Depends on**: SF-02 (committed c1d9520a)

## Shape

`sw implement` already reads the project's `[autonomy]` (SF-01), and its `generate_code` and
`generate_tests` steps name no mode, so the project's `mode` reaches them; an agentic one runs the
coder in its own worktree (SF-02). This sub-feature proves that journey, closes US-3 P-4, and
settles what an agentic `sw implement` does to the user's branch (Q1).

| Piece | Where | Tag |
|---|---|---|
| No code change: the existing merge lands the coder's files as commits on the current branch (Q1) | — | — |
| User guide: `sw implement` under `[autonomy]` | `docs/user_guides/1_installation_and_setup.md` §6b | MODIFY |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the `sw implement` journey | FR-10, NFR-1 | no code changes, so a red cannot come from writing the test first: it comes from the mutants below, which must turn the journey red |

| CB | Tier | Test |
|---|---|---|
| CB-1 | e2e | `sw implement` on a git project with `mode = "agentic"` and a ceiling, the model doubled as a coder: `src/<stem>.py` and `tests/test_<stem>.py` land through the merge as commits on the branch (Q1); a `run_tests` loop-back reruns the coder with the failures in its prompt |
| CB-1 | e2e | the same project with `mode = "oneshot"`: one-shot, nothing new on the branch (NFR-1) |
| CB-1 | integration | a dirty working tree: the run fails, naming "commit or stash", and the tree is left as it was |

## Mutants

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | the project's `mode` never reaching a step that names none (`requested_mode`); the agentic step not isolated (`agentic-in-place`, scope gains the journey) | CB-1 e2e |

## Research Notes

- `_build_implement_pipeline` (`workflows/implementation/interfaces/cli.py:33-100`): `generate_code`
  and `generate_tests` with no `mode`, then `lint_fix`, `run_tests` (loops back on failure),
  `validate_code`.
- An agentic step's per-step worktree is merged by `strip_merge` (`sandboxed_execution.py`): a
  "session snapshot" and a "diff strip merge" commit on the current branch; a dirty real working
  tree makes git refuse, reported as "commit or stash them first" (`worktree_ops.py`).
- Today `sw implement` on a DAL-C/D project writes its files straight into the working tree, with
  no commit.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | An agentic `sw implement` lands its files through the merge: as commits on the current branch, and only on a clean working tree? | yes — the existing merge; a dirty tree stops the run with "commit or stash first" `[agreed 2026-10-20]` |

## Backlog

none
