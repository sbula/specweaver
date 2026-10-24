# Design: The Spend Brake Stops Tool Loops That Have Spent Nothing

- **Feature ID**: TECH-092
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-24, the `TECH-078` closure, reading why the nightly real-model run is red.
  A defect in delivered work (`B-FLOW-05` SF-02, `435e6796`, per-round checks in a tool loop);
  `finished-stories-immutable` bars editing that story, so this ticket owns it.

## Problem Statement

In a tool loop, `LLMCollector.generate_with_tools` (`infrastructure/llm/collector.py:187`) reserves
each round's worst case in `before_request` and keeps every reservation until the whole loop ends
(`held`, recorded once by `_capture`). A finished round's cost is never settled, so
`SpendBudget._ask_to_raise` (`infrastructure/llm/budget.py:217`) counts it as "calls already
running". Measured in the 2026-10-24 nightly log (`.tmp/live/last.log`): the plan step read five
files and was refused at `hosted_spend_per_run = 0.08` with "USD 0.00 of USD 0.08 spent, ... calls
already running may add up to USD 0.07"; a spec review was refused the same way at 0.03. Any user
step that reads a few files can stop early on a small limit. Red today:
`tests/e2e/capabilities/infrastructure/test_spend_brake_live_e2e.py` (2 of 5) and
`tests/e2e/capabilities/workflows/test_plan_live_e2e.py`.

## Candidate Approaches (not yet designed)

- **Settle each round when its answer arrives** `[agreed 2026-10-24]` (the user chose this over
  raising the live tests' limits): the adapters' tool loops report each round's usage; the collector
  records that round's real cost and releases its reservation before the next round is checked.
  Touches every adapter with a tool loop (Gemini, Anthropic, OpenAI-compatible, ...).
- The cost ledger keeps one row per call; whether a round becomes its own row is for the design.

## Non-Goals (proposed, pending design)

- Raising any limit, in tests or defaults.
- The free-tier request budget of the live run (`tests/e2e/gemini_budget.py`).
- Web search (Exa and SearXNG replace Tavily as a capability feature).

## Next Step

Run `specweaver-design` for TECH-092.
