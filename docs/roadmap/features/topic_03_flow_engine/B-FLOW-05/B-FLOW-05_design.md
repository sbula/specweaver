# Design: Spend Brake

- **Feature ID**: B-FLOW-05
- **Phase**: Topic 03 (Flow Engine) · DAL-B (High-Assurance)
- **Status**: APPROVED `[agreed 2026-10-06]`. Built; proven live every night. `🔧` until the user signs off.
- **Story**: `US-4` add-on *Security Defenses* — paths in [US-04.md](../../../stories/US-04.md#spend-brake-b-flow-05)
- **Decisions**: [spend_brake_grilling_2026-10-06.md](../../../../analysis/spend_brake_grilling_2026-10-06.md),
  building on [llm_settings_grilling_2026-09-26.md](../../../../analysis/llm_settings_grilling_2026-09-26.md)
- **Plans**: [SF-01](B-FLOW-05_sf01_implementation_plan.md), [SF-02](B-FLOW-05_sf02_implementation_plan.md)

## Feature Overview

`B-FLOW-05` is the emergency brake on what one run may spend `[agreed 2026-10-06]`. It counts every
call of the run — every role, every server, across `sw resume` — against limits the user writes in
`settings.toml`; none are in code. Before a call could cross a limit, the run **asks**; with nobody
to answer, or on a "no", it parks and `sw resume` continues it. A hosted model with no known price
is refused before the first call.

Measuring models to choose between them is `A-FLOW-01`; loop detection is `B-FLOW-06`.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Spend is measured as it accrues | Brake | SHALL add every completed call's cost and tokens to the run's total for each limit it counts against — including a call that failed partway (a tool loop that raised) and a streamed call's input tokens | the totals are what the run really spent |
| FR-2 | No call can cross a limit unasked | Brake | SHALL, before every request — each tool round included — add the call's worst case to the totals (estimated input tokens × 1.25 plus the output cap; money at the model's prices for a hosted server, tokens for a private one) and ask first if any limit would be crossed `[agreed 2026-10-06]` | a runaway is stopped before the call that would cross the line |
| FR-3 | The stop reaches the user | Handlers, runner | SHALL let the brake's signal through every handler; the runner SHALL turn it into a park, never a step error, a retry or text. The stop is told once, without a traceback, and the park message names the limit `[agreed 2026-10-10]` | the run says *you reached your limit*, not "drift analysis failed" |
| FR-4 | One warning first | Brake | SHALL warn once at 80% of each limit `[agreed 2026-10-06]` | a long run can be watched before it stops |
| FR-5 | Limits come from the settings file | Brake | SHALL take every limit from the machine `settings.toml` and none from code: `[brake] hosted_spend_per_run` (configured currency) for calls to non-private servers, `[brake] tokens_per_run` for calls to private servers `[agreed 2026-10-06]`, and a model's `spend_per_run` / `tokens_per_run` `[agreed 2026-10-03]`; a role carries no limit `[agreed 2026-10-09]` | one place, and the user's own numbers |
| FR-6 | Pause and ask | Brake | SHALL, at a limit and with someone to answer, ask — one question at a time, however many calls run in parallel — naming the limit, what was spent and what running calls may add `[agreed 2026-09-26]`; "yes" raises that limit by its own size (20 → 40 → 60) `[agreed 2026-10-06]` | the user decides, with the numbers in front of them |
| FR-7 | Park when nobody answers | Runner | SHALL park the run at a limit when nobody can answer (no TTY, nightly, CI) or the answer is "no" `[agreed 2026-10-06]`; after a "no" the run asks nothing more and spends nothing more `[agreed 2026-10-08]` | no work is lost, and nothing is spent unasked |
| FR-8 | Resume keeps the totals | Runner, brake | SHALL save the brake's totals and raised limits with the run before it parks, and `sw resume` SHALL continue from them; a limit the user raised in `settings.toml` meanwhile counts if it is higher | a parked run cannot buy a fresh budget by resuming |
| FR-9 | Refuse what cannot be bounded | Brake | SHALL refuse, before the first call, a hosted model with no known price `[agreed 2026-09-26]`, naming the key that would allow it; one whose `thinking_in_output_cap` is not `true` runs with one warning naming the key `[agreed 2026-10-09]` | no hosted call has an unknown price |
| FR-10 | REST stops with a named error | REST API | SHALL answer a request that reaches a limit with HTTP 402 `SPEND_LIMIT` naming the limit, never a bare 500 `[agreed 2026-10-06]` | an API client can tell a spent budget from a crash |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface |
|---|---|---|
| FR-1, FR-2 | each call's tokens, price, output cap | `C-FLOW-13` · `Catalogue.facts(kind, model, overrides)`; `GenerationConfig.max_output_tokens` |
| FR-1 | a call's cost | `C-FLOW-01` · `estimate_cost(usage, facts)` |
| FR-2 | a check before each tool round | adapters call the collector's `before_request(round, prompt_chars)` hook; the collector calls `SpendBudget.before_call` |
| FR-5 | limits | `C-FLOW-13` · `brake_limits(files)`, `ModelFacts.spend_per_run`, `ServerEntry.private` |
| FR-3, FR-7 | turning the signal into a park | `D-FLOW-01` · `execute_step`, `park_run`; handlers log a stop with `log_step_failure` |
| FR-6 | asking | the CLI's `ask_to_spend`, built from the `ContextProvider` |
| FR-8 | saving with the run | `D-FLOW-01` · `PipelineRun.spend_state` in `pipeline_state.db` |
| FR-10 | the error shape | `SpecWeaverAPIError(detail, error_code, status_code)` |

`FR-3`, `FR-7` and `FR-8` cross `infrastructure.llm` → `core.flow`; `FR-6` crosses into
`interfaces.cli`; `FR-10` into `interfaces.api`. Each is a seam FR, proven at integration tier or by
the e2e paths in `US-04.md`.

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

## Architectural Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| AD-1 | The brake asks through a callback the command passes in, built from the `ContextProvider` by the CLI; `infrastructure.llm` imports nothing from `workspace` or `interfaces` | keeps the LLM layer free of UI; REST passes none and so stops (FR-10) |
| AD-2 | Without an answer the brake raises `SpendLimitReachedError` (a `BudgetExceededError`); `execute_step` maps the step's refusal to `WAITING_FOR_INPUT`, so the run parks through `park_run` | one park path; no new run status |
| AD-3 | The brake's totals and raised limits are a JSON field on the persisted run | the run is what parks and resumes, so its spend belongs with it |
| AD-4 | The worst-case check lives in one place, `SpendBudget.before_call`, reached through the collector; adapters report each round through `before_request` | one rule, one method |
| AD-5 | REST answers HTTP 402 with `error_code = "SPEND_LIMIT"` `[agreed 2026-10-06]` | 402 *Payment Required* says money, not a fault |
| AD-6 | **A resume pays again for work already done** — the parked step re-runs from its start, and a fan-out's resume re-runs every sub-run. The paid work stays counted, so the brake still holds `[agreed 2026-10-08]` | reusing paid answers needs its own design; revisit when real runs show what the repeats cost |

## Accepted limits

- A resume pays again for a step already paid (AD-6) `[agreed 2026-10-08]`.
- Queued calls reserve their worst case before their parallel slot opens `[agreed 2026-10-08]`.

## Developer Guides

| Guide | What it says |
|---|---|
| `adding_llm_adapters.md` | a tool loop calls `before_request` before each round |
| `pipeline_engine_guide.md` | a handler never swallows `BudgetExceededError`; it logs failures with `log_step_failure` |

## Non-Goals

- Loop detection — `B-FLOW-06`.
- Limits per model × kind of task × DAL — `B-FLOW-07` `[agreed 2026-10-08]`.
- Choosing or comparing models — `A-FLOW-01`.
- A monthly limit — providers' billing does that; `sw costs` shows month-to-date `[agreed 2026-09-26]`.
- Downgrading or switching the model at a limit `[agreed 2026-09-26]`.
- Counting tokens exactly through the providers' counting endpoints `[agreed 2026-10-06]`.
- The agentic runtime's own turn count (`AutonomySettings.max_turns`) — `C-FLOW-11`.

## Sub-Features

| SF | Scope | FRs | Plan | Committed |
|----|-------|-----|------|-----------|
| SF-01 | Accounting and limits | FR-1, FR-2, FR-4, FR-5, FR-9 | [sf01](B-FLOW-05_sf01_implementation_plan.md) | ✅ |
| SF-02 | Pause, park and resume; REST | FR-3, FR-6, FR-7, FR-8, FR-10 | [sf02](B-FLOW-05_sf02_implementation_plan.md) | ✅ |
