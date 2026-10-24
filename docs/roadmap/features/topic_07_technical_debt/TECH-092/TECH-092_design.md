# Design: The Spend Brake Stops Tool Loops That Have Spent Nothing

- **Feature ID**: TECH-092
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED (by the user, 2026-10-24)
- **Kind**: `bugfix`
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-092/TECH-092_design.md
- **Origin**: 2026-10-24, the `TECH-078` closure, reading why the nightly real-model run is red.
  A defect in delivered work (`B-FLOW-05` SF-02, `435e6796`, per-round checks in a tool loop);
  `finished-stories-immutable` bars editing that story, so this ticket owns it.

## Feature Overview

TECH-092 makes the spend brake settle each round of a tool loop when its answer arrives, so a step
that reads files is judged by what it really spent. It solves a brake that keeps every finished
round's worst-case reservation until the whole loop ends: a plan step that read five files was
refused at a USD 0.08 limit with "USD 0.00 spent, calls already running may add up to USD 0.07".
It touches the four adapters' tool loops (Gemini, Anthropic, OpenAI and its compatible and Qwen
subclasses, Mistral), the rate-limit wrapper and the collector. It does not change any limit, the
cost ledger's rows, or how a single call is checked.

## The Defect (measured 2026-10-24)

- `LLMCollector.generate_with_tools` (`infrastructure/llm/collector.py:187`) reserves the first
  round's worst case, then each later round's in `before_request`, and keeps them all in `held`
  until `_capture` records the whole loop once.
- `SpendBudget.before_call` (`budget.py:185`) refuses when `spent + reserved + this call's worst`
  crosses the limit; the finished rounds sit in `reserved` (shown as "calls already running").
- Each adapter already sums each round's reported usage (`cumulative_usage`) and calls
  `before_request(round_num, prompt_chars)` before every request; the usage never reaches the
  collector before the loop ends.
- Nightly log `.tmp/live/last.log`: `test_plan_live_e2e.py` refused at round 6 (limit 0.08,
  reserved 0.07, spent 0.00); `test_spend_brake_live_e2e.py::test_a_review_under_its_limit_reaches_gemini`
  refused at round 3 (limit 0.03).

## Path List (`ADR-005`)

| Path | Span | Proof |
|---|---|---|
| P-1 a tool loop in any adapter: round *n*'s answer arrives → its usage reaches the brake before round *n+1* is checked | adapter → collector → budget | integration, per adapter, faked HTTP (FR-1, FR-5) |
| P-2 a plan step that reads several files under a small limit, against real Gemini → it completes | flow → planner → collector → Gemini | live, nightly (FR-6) |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | When a tool round's answer arrives, the brake SHALL count that round's reported cost as spent and release its reservation before the next round is checked | collector | settles a round | a finished round is never "already running" |
| FR-2 | A round whose answer reports no usage SHALL count its reserved worst case, as a single call does today | collector | settles a round | an unknown cost is never counted as zero |
| FR-3 | A round SHALL still be refused when what was really spent plus its own worst case crosses the limit | budget | checks a round | the brake is no weaker than for a single call |
| FR-4 | A loop's spent total SHALL equal the sum of its rounds' costs, counted once, also when the loop fails part-way; the cost ledger keeps one row per call | collector | records the loop | no round is counted twice or lost |
| FR-5 | Every adapter with a tool loop SHALL hand each round's usage to the round hook: Gemini, Anthropic, OpenAI (with its compatible and Qwen adapters), Mistral; the rate-limit wrapper passes it through | adapters | report a round | the fix reaches every provider (seam) |
| FR-6 | The nightly live run's spend-brake and plan tests SHALL pass again with their limits unchanged | live run | runs | the defect is proven fixed against a real provider |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1, FR-5 | each round's `TokenUsage` | the adapters' `cumulative_usage` and `before_request` hook | read 2026-10-24 (`gemini.py:322`, `anthropic.py:257`, `openai.py:286`, `mistral.py:246`, `_rate_limit.py:96`, `base.py:172`) |
| FR-1, FR-4 | a usage's cost | `telemetry.estimate_cost(usage, prices)`, `SpendBudget.record` | read 2026-10-24 |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | A single call (no tools) is checked and recorded as before **[proof: meta — the full suite before every commit]** | existing tests green |
| NFR-2 | No limit changes, in tests, defaults or settings | none edited |

## External Dependencies

None.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | The round hook carries the usage summed so far: `before_request(round_num, prompt_chars, used_so_far)`; the collector settles the difference since the last round | every adapter already keeps that sum; one hook, no second callback | No |
| AD-2 | The collector keeps the cost ledger's one row per call, written at the end with the loop's total | the ledger's shape is unchanged; only the brake learns earlier | No |

## ROI Analysis

| Item | Effort | Risk |
|------|--------|------|
| 1 sub-feature, 6 FRs | 1 session | low: the hook exists in every adapter; NFR-1 guards single calls |

| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| Users with a spend limit | steps that read files are no longer stopped early | high |
| The nightly live run | green again, so it can judge the real-model paths | high |

### Red/Blue (Phase 6), 2 cycles
- R1 (MEDIUM) a loop that fails after some rounds were settled could count them twice. Blue: the
  failure path records only the usage since the last settled round, against the reservations still
  held (FR-4).
- R2 (MEDIUM) a round's cost with no known price. Blue: the brake already stops before a call whose
  price is unknown; a round with no reported usage counts its worst case (FR-2).
- R3 (LOW) each round's usage includes the whole growing prompt. Blue: that is what the provider
  bills per request; the sum is the real cost.
- Cycle 2: no new finding.

## Works For Real

The nightly live run (`scripts/live.py`): `test_plan_live_e2e.py` and
`test_spend_brake_live_e2e.py` pass with their limits unchanged (FR-6). Run once before sign-off.

## Sub-Feature Breakdown

### SF-01: Settle each tool round
- **Scope**: the round hook carries usage; the collector settles each round; the four adapters and
  the rate-limit wrapper.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6]
- **Depends on**: none

## Execution Order

1. SF-01

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Settle each tool round | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design APPROVED 2026-10-24.
**Next step**: On approval, trigger the implementation-plan skill for SF-01.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume
from there using the appropriate skill.
