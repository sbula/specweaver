# Implementation Plan: The Spend Brake Stops Tool Loops That Have Spent Nothing [SF-01: Settle each tool round]
- **Feature ID**: TECH-092
- **Sub-Feature**: SF-01 — Settle each tool round
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-092/TECH-092_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-092/TECH-092_sf01_implementation_plan.md
- **Status**: APPROVED

## Scope

All six FRs of the design: each tool round settles with the brake when its answer arrives (FR-1),
an unreported round counts its worst case (FR-2), the brake is no weaker (FR-3), the loop is
counted once also on failure (FR-4), every adapter hands each round's usage over (FR-5), and the
nightly live tests pass with their limits unchanged (FR-6). NFR-1 (single calls as before), NFR-2
(no limit changes). Kind `bugfix`. No dependency.

## Research Notes

Read 2026-10-24.

- **The round hook** `before_request: Callable[[int, int], None]` — `(round_num, prompt_chars)` —
  is declared on `LLMAdapter.generate_with_tools` (`adapters/base.py:172`), passed through by the
  rate-limit wrapper (`adapters/_rate_limit.py:96`), and called before every request by Gemini
  (`gemini.py:322`), Anthropic (`anthropic.py:257`), OpenAI (`openai.py:286`; `QwenAdapter` and
  `OpenAICompatibleAdapter` subclass it) and Mistral (`mistral.py:246`). Each keeps
  `cumulative_usage` (the sum of every round's reported `TokenUsage` so far) and attaches it to an
  exception (`errors.attach_usage`).
- **The collector** (`infrastructure/llm/collector.py:187`): `_reserve` reserves round 0; the
  hook reserves rounds ≥ 1 (`held.append(budget.before_call(scope, worst))`) and widens the
  pending ledger row (`_widen`); on success `_capture` writes the ledger row and calls
  `budget.record(scope, cost_of_total_usage, Reservation.combined(held))`; on failure
  `_record_failure(scope, combined, exc)` counts `exc.usage` or the reserved worst case.
- **The budget** (`budget.py`): `before_call` refuses when `spent + reserved + worst` crosses a
  limit; `record(scope, cost, reservation)` releases the reservation and adds `cost`, or the
  reserved amount when `cost` is `None` or has no money for a money limit. A `TokenUsage()` (all
  zeros) reply counts its worst case (`collector.py:318`).
- **Costing a usage**: `telemetry.estimate_cost(usage, prices) -> float | None`; a `Cost(usd,
  tokens)` with `usd=None` counts the reserved worst case in `record`.
- **Tests that pin the defect**: `test_collector_circuit_breaker.py::test_every_tool_round_is_checked_before_its_request`
  expects a 5-round loop of 200-token rounds to stop after 3 (it counts reservations, not cost).
  Hook doubles that take two arguments: `test_collector.py`, `test_rate_limit.py`,
  `test_collector_circuit_breaker.py`, `test_every_call_in_the_ledger.py`, `test_anthropic.py`,
  `test_openai.py`, `test_mistral.py`, `test_adapters.py`.

## Approach (pseudocode, ordered)

**CB-1 — the collector settles each round (FR-1..FR-4, NFR-1)**
1. The hook becomes `before_request(round_num, prompt_chars, used_so_far: TokenUsage)`
   (design AD-1); `base.py` and the rate-limit wrapper declare and pass it.
2. In `generate_with_tools`, the collector keeps `settled: TokenUsage` (what the brake has
   counted) and the reservations not yet settled. In the hook, for a round ≥ 1, in this order:
   a. `delta = used_so_far − settled`; record it against the reservations held so far
      (`budget.record(scope, cost_of(delta), combined(held))`; a zero `delta` → `None` cost, the
      worst case, FR-2); `settled = used_so_far`; `held = []`.
   b. then reserve this round as today (`before_call`), so FR-3's check sees the real spend.
   Settling before reserving is the fix; reserving first is the defect.
3. On success, `_capture` records only `total − settled` against what is still held; the ledger
   row still carries the loop's total (design AD-2).
4. On failure, `_record_failure` counts `exc.usage − settled` against what is still held (FR-4).

**CB-2 — every adapter hands the usage over (FR-5, FR-6)** — closes SF-01
5. Gemini, Anthropic, OpenAI, Mistral pass `cumulative_usage` as the hook's third argument.
6. The live run: `test_plan_live_e2e.py` and `test_spend_brake_live_e2e.py` once, limits unchanged.

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| unit | a 5-round loop of cheap rounds under a limit that holds 3 worst cases completes; spent equals the summed real cost | FR-1 | rounds 4–5 are refused today |
| unit | a round that reports no usage counts its worst case | FR-2 | no per-round settlement exists |
| unit | rounds whose real cost crosses the limit are refused at the round that would cross it | FR-3 | (rewrites `test_every_tool_round_is_checked_before_its_request`, which counted reservations) |
| unit | a loop failing in round 3 counts rounds 1–2 once plus its attached remainder; a finished loop's spent equals its total | FR-4 | double count / reservations left |
| unit | the ledger keeps one row per call with the loop's total | FR-4, AD-2 | — (guard: must stay green) |
| integration | per adapter (Gemini, Anthropic, OpenAI, Mistral) with faked HTTP: a 3-round tool loop through the real collector settles each round; the hook sees the usage summed so far | FR-5 (seam: adapter → collector → budget) | the hook gets no usage |
| live | `test_plan_live_e2e.py`, `test_spend_brake_live_e2e.py` with real Gemini | FR-6 | refused today (nightly log 2026-10-24) |

Mutants (into `TECH-092_mutants.json`): reserve before settling (the defect back); settle nothing
(`delta` ignored); count `total` instead of `total − settled` at the end (double count); the
failure path ignoring `settled`; each adapter passing `TokenUsage()` instead of its sum.

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–4, the unit tests, the hook doubles updated | full suite green; FR-1..FR-4 mutants killed |
| CB-2 | steps 5–6, the adapter integration tests, the live run | full suite green; FR-5 mutants killed; the live tests pass; stage and stop (closes SF-01) |

## Documentation

`docs/dev_guides/adding_llm_adapters.md` (it describes `before_request`): the hook's third
argument, the usage summed so far, and that a round settles with the brake when its answer arrives. `.agents/STATE.md`: the "spend brake stops tool loops" line
goes at sign-off.

## Architecture Verification (Phase 3)

- All changes stay inside `infrastructure/llm` (adapters, collector, budget); no new import, no
  module boundary crossed; `tach` unchanged.
- The hook is internal to `infrastructure/llm` (adapters and their collector); no other module calls
  `generate_with_tools` with `before_request` (checked: `grep before_request src` lists only these).

## Audit (Phase 2) and Consistency (Phase 5)

- No open question: the approach is the user's choice `[agreed 2026-10-24]`; the unknown-cost and
  unknown-price rules already exist; no limit, ledger shape or user-facing name changes.
- Every FR has a step, a test and a mutant; NFR-1 by the full suite; NFR-2 by no edits to limits.
- Red/Blue, 2 cycles:
  - R1 (MEDIUM) Anthropic and OpenAI report cached and cache-write tokens per round. Blue:
    `estimate_cost` already bills each kind; `delta` subtracts the whole `TokenUsage`.
  - R2 (MEDIUM) `TokenUsage` has `__add__` (`models.py:127`) but no subtraction. Blue: add
    `__sub__` beside it, field by field, with its own unit test (CB-1).
  - R3 (LOW) a round's settled cost lands before `_widen` updates the pending row. Blue: the row
    is the ledger's, the settlement the brake's; neither reads the other.
  - Cycle 2: no new finding.
