# Implementation Plan: Spend Brake [SF-02: Pause, park and resume]
- **Feature ID**: B-FLOW-05
- **Sub-Feature**: SF-02 — Pause, park and resume
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-05/B-FLOW-05_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-05/B-FLOW-05_sf02_implementation_plan.md
- **Status**: APPROVED `[agreed 2026-10-07]`

## Goal

At a limit the run asks, and "yes" goes on by one step of that limit; "no" or nobody to ask parks
the run, and `sw resume` continues with the totals it had. REST answers 402 `SPEND_LIMIT`.
FR-3, FR-6, FR-7, FR-8, FR-10, plus SF-01's carry-overs: the US-04 S5 e2e and the round check's
prompt growth.

## Where it plugs in (measured 2026-10-07)

| Need | Surface | Read |
|---|---|---|
| The check | `SpendBudget.before_call(scope, worst) -> Reservation` (sync), raising `SpendLimitReachedError` | `infrastructure/llm/budget.py` |
| Its callers | `TelemetryCollector.generate*` (async); the round hook passed to the adapters as `on_tool_round` (sync) | `collector.py` |
| Asking | `ContextProvider.ask(question, *, section="") -> str` (async), `HITLProvider`; attached only with a TTY | `workspace/context/provider.py:31`, `interfaces/cli/main.py:136` |
| A step's escape | `execute_step` turns every exception into `StepStatus.ERROR` | `core/flow/engine/step_execution.py:183-216` |
| Parking | a handler returning `WAITING_FOR_INPUT` → `park_run(...)` | `step_execution.py:220`, `:470` |
| Handlers that swallow | ~50 `except Exception` blocks across handlers and workflows; `drift` turns the stop into text | research 2026-10-06 |
| The stored run | `flow_pipeline_runs` columns, `StateStore.save_run` / `load_run`; schema migrations by version (`ALTER TABLE … ADD COLUMN`) | `core/flow/engine/store.py:34`, `:180-207` |
| Resume | `PipelineRunner.resume(run_id)` loads the run; `sw resume` rebuilds the router | `runner.py:177`, `core/flow/interfaces/cli.py:482` |
| REST errors | `SpecWeaverAPIError(detail, error_code, status_code)` | `interfaces/api/errors.py:16` |

## Decisions (audit)

| # | Question | Options | Proposal |
|---|----------|---------|----------|
| Q-1 | What pressing Enter at the pause means | (a) no — the run parks; (b) yes — the run goes on | **(a)** `[agreed 2026-10-07]` — spending more needs a deliberate yes |
| Q-2 | How a swallowed stop still parks the run (FR-3) — technical | (a) the brake remembers that it stopped; after every step the runner asks the router's budget and parks if so, whatever the handler did with the error; (b) edit each of ~50 broad `except` blocks | **(a)** `[agreed 2026-10-07]` — one place, and a new handler cannot break it. `Reviewer` keeps re-raising |

## Changes

**CB-1 — the question, and the park** · FR-3, FR-6, FR-7

1. `SpendBudget` gains an optional `ask(limit, spent, worst, overshoot) -> bool` (async) and a
   lock, so one question is asked at a time. `before_call` becomes async: on a crossing it asks;
   "yes" raises that limit by its own value and checks again; "no", or no `ask`, raises
   `SpendLimitReachedError` and records it as the budget's `stopped`.
2. The round hook becomes async: the adapters await a new `before_request(round_num, prompt_chars)`
   before each request; `prompt_chars` is the size of the payload they are about to send, so the
   check sees tool results as the prompt grows (SF-01 carry-over). `on_tool_round` is unchanged.
3. `command_router` passes an `ask` built from the run's `ContextProvider` (TTY only); REST passes
   none.
4. The runner, after each step: if the router's budget has `stopped`, the step is parked
   (`WAITING_FOR_INPUT`), whatever its handler returned (Q-2). `sw run` prints the limit, what was
   spent and `sw resume <id>`.

**CB-2 — resume with the totals; REST 402** · FR-8, FR-10

5. `flow_pipeline_runs` gains a `spend_state` column (schema v4): spent per key and each raised
   limit, as JSON. The runner saves it with the run; `resume` restores it into the new router's
   budget. On resume a limit is the higher of the file's value and the raised one.
6. `POST /review`, `/implement` and the API pipeline runs map `SpendLimitReachedError` to
   `SpecWeaverAPIError(..., "SPEND_LIMIT", 402)` naming the key.
7. Docs: installation guide (the pause, the park, `sw resume`), `pipeline_engine_guide.md` (a
   handler need not re-raise; the runner parks).

Code comments stay short and say only what the code does `[agreed 2026-10-06]`.

## Tests

| Tier | Bucket | Test | FR | CB |
|---|---|---|---|---|
| Unit | Happy | "yes" raises the limit by its value (20 → 40) and the call goes on | FR-6 | 1 |
| Unit | Hostile | two calls cross at once → one question, not two | FR-6 | 1 |
| Unit | Boundary | Enter (empty answer) → no → stopped | FR-6, FR-7 | 1 |
| Unit | Degradation | no `ask` → stopped, nothing sent | FR-7 | 1 |
| Unit | Boundary | the round check counts the payload the adapter is about to send | FR-2 | 1 |
| Integration | Seam | a `drift` step whose call is stopped → the run parks, not "LLM analysis failed" (US-04 S7) | FR-3 | 1 |
| E2E (US-04 S1) | Journey | `sw run` in a terminal crosses → asked; "yes" → goes on | FR-6 | 1 |
| E2E (US-04 S5) | Journey | a tool round that would cross → asked before that round's request | FR-2, FR-6 | 1 |
| E2E (US-04 S2) | Journey | "no" → parks; `sw resume` → continues with the spent totals, asks again at the limit | FR-7, FR-8 | 2 |
| Integration | Seam | save → load → restore: spent and raised limits survive; a higher file value wins | FR-8 | 2 |
| Integration | Boundary | a v3 state DB migrates to v4 with `spend_state` empty | FR-8 | 2 |
| E2E (US-04 S6) | Journey | `POST /implement` at a limit → 402 `SPEND_LIMIT` naming the key | FR-10 | 2 |

Mutants to record: "yes" does not raise the limit; the lock dropped; Enter read as yes; the
runner's stopped check removed; spend not saved, or not restored; the payload size ignored in the
round check; REST mapping removed.

## Research Notes

- `ContextProvider.ask` is async, so the check that asks must be async; the adapters' existing
  `on_tool_round` hook is sync and is used by review handlers, so a separate async hook is added
  rather than changing it.
- `execute_step` catches every exception (`step_execution.py:208`); without Q-2 (a) a stop inside a
  handler that catches `Exception` would become a step error and a retry gate would hit it again.
- The state DB already migrates by version with `ALTER TABLE … ADD COLUMN` (`store.py:180`).

## Red/Blue review (2026-10-07, 2 cycles)

| # | Finding | Severity | Resolution |
|---|---|---|---|
| R-1 | `before_call` turning async breaks SF-01's callers and tests | MEDIUM | all callers are already async; the tests move to `await` in CB-1 |
| R-2 | The lock must belong to the running event loop | MEDIUM | created on first use inside `before_call` |
| R-3 | Routers built by hand in tests (`FixedRouter`) have no budget | LOW | the runner reads the budget with a default of none |
| R-4 | The question during a run's live progress display | LOW | asked through the same `ContextProvider` the drafting step already uses mid-run |

Cycle 2 re-checked the bindings and the boundaries; nothing above LOW.

