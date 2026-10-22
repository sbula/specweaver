# Design: Every Workflow Calls the Model Its Own Way

- **Feature ID**: TECH-085
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 9 below.

## Problem Statement

Each workflow has its own prompt, call, parse and retry; six answer cleaners exist (one breaks on a
bare fence); one prompt is a raw string join; mentioned files are injected escaped in one place and
raw in another.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **WV-4** — Six fence and JSON cleaners for model answers; `decomposer` breaks on a bare fence.
  Where: `planner.py:182`, `decomposer.py:112`, `scenario_generator.py:200`, `generator.py:113`,
  `arbiter.py:404`, `enricher.py:90`.
- **WV-5** — Each workflow has its own call, tool branch, parse and retry; budget errors re-raised
  in one only. Where: `planner.py:122`, `scenario_generator.py:101`, `decomposer.py:99`,
  `reviewer.py:186`, `generator.py:99`.
- **WV-6** — Builds its prompt by string join, no escaping, no budgeting, no constitution preamble;
  wrong adapter argument on the no-tools path. Where: `scenario_generator.py:140,209-283`.
- **Real defect 2** — Sends a plain string when the model has no tool support; breaks the first
  adapter without tools. Where: `workflows/scenarios/scenario_generator.py:140`.
- **WV-8** — Mentioned files injected two ways: one escaped and capped, one raw. Where:
  `prompt/adders.py:388` vs `handlers/review.py:69`.
- **WV-15** — The provider tool loop copied four times. Where: `adapters/openai.py:207`,
  `mistral.py:194`, `anthropic.py:207`, `gemini.py:255`.
- **FL-22** — Routing wrappers add nothing; the guard is repeated with different texts. Where:
  `review.py:29`, `generation.py:40,338`; 8 "LLM not configured" checks.
- **WV-16** — Back-compat shims still used inside; two names per method. Where: `prompt_builder.py`,
  `_prompt_*.py`, `adders.py:163`.
- **WV-17** — Providers, prompts, ledger, prices, HTTP price refresh and budget behind one "adapter"
  manifest. Where: `infrastructure/llm/`.

## Goal

Every model call goes through one prompt builder and one structured-call helper.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-085`. Write each fix's test
red
first.
