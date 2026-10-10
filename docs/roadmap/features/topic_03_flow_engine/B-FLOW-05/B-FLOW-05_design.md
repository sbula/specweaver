# Design: Spend Brake

- **Feature ID**: B-FLOW-05
- **Phase**: Topic 03 (Flow Engine) · DAL-B (High-Assurance)
- **Status**: APPROVED `[agreed 2026-10-06]` — redesign after `C-FLOW-13`; the capability stays `🔧` until it is built and proven
- **Design Doc**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-05/B-FLOW-05_design.md
- **Story**: `US-4` add-on *Security Defenses* — paths in [US-04.md](../../../stories/US-04.md#spend-brake-b-flow-05)
- **Decisions**: [spend_brake_grilling_2026-10-06.md](../../../../analysis/spend_brake_grilling_2026-10-06.md),
  building on [llm_settings_grilling_2026-09-26.md](../../../../analysis/llm_settings_grilling_2026-09-26.md)
- **Plan of the built version**: [B-FLOW-05_implementation_plan.md](B-FLOW-05_implementation_plan.md)

## Feature Overview

`B-FLOW-05` is the emergency brake on what one run may spend `[agreed 2026-10-06]`. Measuring
models to choose between them is `A-FLOW-01`, and loop detection is `B-FLOW-06`. The brake counts
every call of the run — every role, every server, across `sw resume` — against limits the user
writes in `settings.toml`, and none written in code. Before a call could cross a limit, the run
**pauses and asks**; with nobody to answer, or on a "no", it parks and `sw resume` continues it.
A hosted model with no known price, or whose output cap may not bound its thinking, is refused
before the first call.

## Research Findings

### Codebase Patterns

Measured 2026-10-06 (research of `src/specweaver`):

- **One budget per command already.** `build_router` builds one `SpendBudget` from `[brake]`
  (`infrastructure/llm/router.py:49-72`); `RoleResolver` hands it to one `TelemetryCollector` per
  server (`resolve.py:57`, `:116`). The collector checks before `generate`, `generate_with_tools`
  and `generate_stream` and records after (`collector.py:79`, `:93`, `:115`, `:166`).
- **What the built brake does not do.**
  - It checks only what is already spent, never the next call's worst case.
  - It checks once before a whole tool loop, not before each round (`collector.py:93`).
  - It records nothing when a tool loop raises, so those rounds' tokens are lost.
  - A streamed call records no input tokens (`collector.py:125-133`).
  - An unpriced call adds 0 USD.
  - Model and role limits are stored but not applied.
- **A stop is not a pause.** `execute_step` turns every exception into `StepStatus.ERROR`
  (`core/flow/engine/step_execution.py:208`); a retry gate then hits the spent budget again. Only a
  handler returning `WAITING_FOR_INPUT` parks (`step_execution.py:470`, `park_run` at `:220`).
- **Handlers that hide the stop.** `drift.py:175-177` turns it into text and the step goes on;
  `lint_fix`, `standards`, `arbiter`, `scenario`, `dual_pipeline`, `draft` turn it into a step error.
  Only `Reviewer` re-raises it (`workflows/review/reviewer.py:198`).
- **Resume forgets.** `sw resume` rebuilds the router through `_build_run_context` → `_wire_models`,
  so the budget restarts at zero (`core/flow/interfaces/cli.py:482`).
- **Asking exists.** `ContextProvider.ask(question, *, section="") -> str`
  (`workspace/context/provider.py:31`), implemented by `HITLProvider`
  (`interfaces/cli/hitl_provider.py:22`), attached to `RunContext.context_provider` only with a TTY
  (`interfaces/cli/main.py:136`).
- **REST.** A `BudgetExceededError` in `POST /implement` reaches FastAPI as a bare 500
  (`interfaces/api/app.py:80` handles only `SpecWeaverAPIError`).
- **Token estimates.** Every adapter but Gemini counts `len(text) // 4` (`adapters/base.py:144`).

### External Tools

None. The brake reads only what the adapters already return.

### Blueprint References

None.

## Functional Requirements

FR-1 to FR-5 keep their numbers so the tests that cite them stay valid; their wording is new.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Spend is measured as it accrues | Brake | SHALL add every completed call's cost and tokens to the run's totals, by server privacy, by model and by role — including a call that failed partway (a tool loop that raised) and a streamed call's input tokens | the totals are what the run really spent |
| FR-2 | No call can cross a limit unasked | Brake | SHALL, before every request — each tool round included — add the call's worst case to the totals (estimated input tokens × 1.25 plus the output cap; in money at the model's prices for a hosted server, in tokens for a private one) and pause first if any limit would be crossed `[agreed 2026-10-06]` | a runaway is stopped before the call that would cross the line |
| FR-3 | The pause reaches the user | Handlers, runner | SHALL let the brake's signal through every handler, and the runner SHALL turn it into a pause, never into a step error, a retry or text | the run says *you reached your limit*, not "drift analysis failed" |
| FR-4 | One warning first | Brake | SHALL warn once at 80% of each limit `[agreed 2026-10-06]` | a long run can be watched before it pauses |
| FR-5 | Limits come from the settings file | Brake | SHALL take every limit from the machine `settings.toml` and none from code: `[brake] hosted_spend_per_run` (configured currency) for calls to non-private servers, `[brake] tokens_per_run` for calls to private servers `[agreed 2026-10-06]`, and a model's `spend_per_run` / `tokens_per_run` `[agreed 2026-10-03]`; a role carries no limit `[agreed 2026-10-09]` | one place, and the user's own numbers |
| FR-6 | Pause and ask | Brake | SHALL, at a limit and with someone to answer, ask — one question at a time, however many calls run in parallel — naming the limit, what was spent and any overshoot by calls already running `[agreed 2026-09-26]`; "yes" raises that limit by its own size (20 → 40 → 60) `[agreed 2026-10-06]` | the user decides, with the numbers in front of them |
| FR-7 | Park when nobody answers | Runner | SHALL park the run at a limit when nobody can answer (no TTY, nightly, CI) or the answer is "no" `[agreed 2026-10-06]` | no work is lost, and nothing is spent unasked |
| FR-8 | Resume keeps the totals | Runner, brake | SHALL save the brake's totals and raised limits with the run before it parks, and `sw resume` SHALL continue from them; a limit the user raised in `settings.toml` meanwhile counts if it is higher | a parked run cannot buy a fresh budget by resuming |
| FR-9 | Refuse what cannot be bounded | Brake | SHALL refuse, before the first call, a hosted model with no known price `[agreed 2026-09-26]`, naming the key that would allow it; one whose `thinking_in_output_cap` is not `true` runs with one warning naming the key `[agreed 2026-10-09]` | no hosted call has an unknown price |
| FR-10 | REST stops with a named error | REST API | SHALL answer a request that reaches a limit with an HTTP error naming the limit, never a bare 500 `[agreed 2026-10-06]` | an API client can tell a spent budget from a crash |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1, FR-2 | each call's tokens, price, output cap | `C-FLOW-13` · `Catalogue.facts(kind, model, overrides) -> ModelFacts \| None`; `GenerationConfig.max_output_tokens` | read `infrastructure/llm/catalogue.py:62`, `infrastructure/llm/models.py` |
| FR-1 | a call's cost | `C-FLOW-01` · `estimate_cost(usage, facts) -> float \| None` | read `infrastructure/llm/telemetry.py:49` |
| FR-2 | a check inside each tool round | adapters · the loop over `tool_rounds(config)` | read `adapters/anthropic.py:235`, `models.py:83` — the collector cannot see rounds today; the adapters gain a per-round check |
| FR-2 | the prompt's size | adapters · `count_tokens(text, model)`, `estimate_tokens(text)` | read `adapters/base.py:122`, `:144`; `adapters/gemini.py:377` |
| FR-5 | limits | `C-FLOW-13` · `brake_limits(files)`, `ModelFacts.spend_per_run`, `ServerEntry.private` | read `core/config/llm_settings.py:97`, `:132`, `:159` |
| FR-5 | which role a call is for | `C-FLOW-13` · `GenerationConfig.task_type`, set by `llm_for(context, task_type)` | read `core/flow/handlers/_llm.py:46` — REST calls leave it `UNKNOWN`; FR-5 has them stamp it |
| FR-3, FR-7 | turning the signal into a park | `D-FLOW-01` · `execute_step(...)`, `park_run(runner, run, step_def, step_idx, total, result)` | read `core/flow/engine/step_execution.py:183`, `:220` |
| FR-6 | asking | `ContextProvider.ask(question, *, section="") -> str` | read `workspace/context/provider.py:31`, `interfaces/cli/main.py:136` |
| FR-8 | saving with the run | `D-FLOW-01` · `PipelineRun` in `pipeline_state.db`; `PipelineRunner.resume(run_id)` | read `core/flow/engine/state.py:46`, `runner.py:177` |
| FR-10 | the error shape | `SpecWeaverAPIError(detail, error_code, status_code)` | read `interfaces/api/errors.py:16` |

`FR-3`, `FR-7` and `FR-8` cross `infrastructure.llm` → `core.flow`; `FR-6` crosses into
`interfaces.cli`; `FR-10` into `interfaces.api`. Each is a **seam FR**, proven at integration tier
or by the e2e paths in `US-04.md`.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Fail closed | Unknown is never a pass: an unknown price refuses (FR-9); an unknown thinking cap warns; a limit must be `> 0`; an unset `[brake]` value refuses the command (`C-FLOW-13`) |
| NFR-2 | Scope | One brake per run, covering the whole call tree and surviving `sw resume` `[agreed 2026-09-26]` |
| NFR-3 | No limit in code | No number or default for any limit in `src/` `[agreed 2026-10-03]` |
| NFR-4 | Proven live, nightly | Against real Gemini each night: a review under its limit goes through, one below a call's worst case is stopped before sending; under USD 0.10 a night `[agreed 2026-10-10]` |

## Live demo

With a `[servers.gemini]` server, a role on `gemini-3.8-flash` and `GEMINI_API_KEY` set:

- `[brake] hosted_spend_per_run = 0.10`, then `sw review <spec>` → a verdict; `sw costs` shows the spend.
- `hosted_spend_per_run = 0.001`, then the same → "`brake.hosted_spend_per_run` would be crossed",
  and nothing is sent.

Nightly: `python scripts/live.py` (in the nightly session); last result: `python scripts/live.py --status`.

## External Dependencies

None.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | The brake asks through a callback the command passes in (`ask_to_continue`), built from the `ContextProvider` by the CLI; `infrastructure.llm` imports nothing from `workspace` or `interfaces` | keeps the LLM layer free of UI; REST passes none and so stops (FR-10) | No |
| AD-2 | Without an answer the brake raises `SpendLimitReachedError` (a `BudgetExceededError`), which `execute_step` maps to `WAITING_FOR_INPUT`, so the run parks through the existing `park_run` | reuses the one park path; no new run status | No |
| AD-3 | The brake's totals and raised limits are a JSON field on the persisted run in `pipeline_state.db` | the run is what parks and resumes, so its spend belongs with it | No — a new field in the run-state store, not a new store |
| AD-4 | The worst-case check is in the adapters' tool loop as well as in the collector, through one `SpendBudget.before_call(...)` | the collector cannot see rounds; one method keeps one rule | No |
| AD-5 | REST answers HTTP 402 with `error_code = "SPEND_LIMIT"` `[agreed 2026-10-06]` | 402 *Payment Required* says money, not a fault | No |
| AD-6 | **A resume pays again for work already done** — the parked step re-runs from its start, and a fan-out's resume re-runs every sub-run. The paid work stays counted, so the brake still holds `[agreed 2026-10-08]` | saving each finished model answer for reuse needs its own design; revisit when real runs show what the repeats cost | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| Accounting: totals by privacy, model, role; worst case; failed and streamed calls | medium | low — pure logic, well tested today |
| Pause, park, resume with saved totals | medium | medium — touches the runner and every LLM handler |
| REST error, rename, docs | low | low |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| The user running hosted models | no run spends past a limit without being asked | high |
| The user running the GB10 | a runaway local model is stopped by tokens, per model | medium |
| Nightly and CI runs | a limit parks instead of failing, so the work survives | medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| A handler still hides the signal | medium | high | one integration test per LLM handler; a scan test that no handler catches it without re-raising |
| The estimate is low and a call overshoots | medium | low | 25% margin (Q12); the pause reports the overshoot (FR-6) |
| Many models refused by FR-9 | low | medium | the message names the one key to set; only Mistral and hosted Qwen are unknown today |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `drift` handler | swallows the brake into text | fixed by FR-3 | low |
| `TelemetryCollector` streaming | input tokens never recorded | fixed by FR-1 | low |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `adding_llm_adapters.md` | a tool loop calls `budget.before_call` each round | ⬜ To be written during Pre-commit |
| `pipeline_engine_guide.md` | a handler never catches `BudgetExceededError` without re-raising | ⬜ To be written during Pre-commit |

## Non-Goals

- Loop detection — `B-FLOW-06`.
- Limits per model × kind of task × DAL — `B-FLOW-07` `[agreed 2026-10-08]`.
- Choosing or comparing models — `A-FLOW-01`.
- A monthly limit — providers' billing does that; `sw costs` shows month-to-date `[agreed 2026-09-26]`.
- Downgrading or switching the model at a limit `[agreed 2026-09-26]`.
- Reusing paid model answers when a run resumes — deferred, see AD-6 `[agreed 2026-10-08]`.
- Counting tokens exactly through the providers' counting endpoints `[agreed 2026-10-06]`.
- The agentic runtime's own turn count (`AutonomySettings.max_turns`, not yet wired) — `C-FLOW-11`.

## Sub-Feature Breakdown

### SF-01: Accounting and limits
- **Scope**: every call is counted and checked against every limit before it is sent.
- **FRs**: [FR-1, FR-2, FR-4, FR-5, FR-9]
- **Inputs**: `[brake]`, model limits, catalogue facts, each call's config and usage
- **Outputs**: a `SpendBudget` that refuses or signals a limit before a call; `SpendLimitReachedError`
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-05/B-FLOW-05_sf01_implementation_plan.md

### SF-02: Pause, park and resume
- **Scope**: a limit becomes a question, or a park the run survives, and REST names it. Also
  carried over from SF-01 `[agreed 2026-10-07]`: the US-04 S5 e2e, and the round check's prompt
  growth (adapters report each round's real prompt size).
- **FRs**: [FR-3, FR-6, FR-7, FR-8, FR-10]
- **Inputs**: `SpendLimitReachedError` from SF-01; the `ContextProvider`; the persisted run
- **Outputs**: paused, parked and resumed runs with their totals; REST 402 `SPEND_LIMIT`
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-05/B-FLOW-05_sf02_implementation_plan.md

## Execution Order

1. SF-01 (no deps)
2. SF-02 (depends on SF-01)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Accounting and limits | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Pause, park and resume | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Redesign APPROVED 2026-10-06. Red/Blue
2026-10-06, two cycles: worst case in tokens for private servers (FR-2), one question at a time
(FR-6), the higher limit wins on resume (FR-8), the agentic turn count named a non-goal.
**Next step**: Both sub-features are built. The capability stays `🔧` until the user approves it.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and
resume from there using the appropriate skill.
