# Design: The Reviewer Uses Up Its Tool Rounds on Gemini

- **Feature ID**: TECH-095
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `audit`
- **Origin**: 2026-11-08, the `TECH-088` live demo. With `brake.agent_turns = 5`, a `sw review` of a
  two-module project against Gemini ended in "the model was still calling tools after 5 rounds",
  verdict ERROR. Two earlier tries got `503 UNAVAILABLE`. The three tries took 58 minutes and about
  13 requests.

## Problem Statement

The reviewer calls `find_files` and `read_file` and may never write its verdict within the round
limit. One review costs up to `agent_turns` requests, and every retry costs them again. The nightly
live run has 20 Gemini requests in total (`tests/e2e/gemini_budget.py`). The night of 2026-11-08
also had one live test fail on the quota. The `TECH-088` demo now runs with one try and
`agent_turns = 2`, so it passes on an ERROR that names the round limit.

## Candidate Approaches (not yet designed)

Asked by the user 2026-11-08:
- Measure on how many runs the reviewer uses up its rounds.
- Find why: a tool loop, or no final verdict.
- Check if a local model does the same.
- Analyse the nightly budget, last night's quota failure included. Three other live tests retry up
  to 5 times (the plan step, Rust `sw implement`, the spend brake), and each retry spends budget.

## Non-Goals (proposed, pending design)

- No change to the review prompt or tools before the measurement says why.

## Next Step

The user places it in the queue. Every measurement run is a real-model call and needs the user's
consent first.
