# Design: Token-Burn Circuit Breakers (EDoS Prevention)

- **Feature ID**: B-FLOW-05
- **Epic**: Topic 03 (Flow Engine)
- **Status**: ✅ Delivered — this document is a **record**, not a plan.
- **DAL**: B (Severe failure)

## What shipped

`src/specweaver/infrastructure/llm/budget.py` holds a run's spend against two ceilings — dollars
and tokens. `TelemetryCollector` checks it before every request and feeds every completed call
back into it. When a ceiling is reached the next request is refused with `BudgetExceededError`.

Both ceilings are configured on `LLMSettings` and **default to a finite value**. A breaker that
ships disabled stops nothing, and the queue entry's premise was that the only existing guard was
`max_retries` — which counts attempts, not money. Three retries at a 200k-token prompt cost what
thirty cheap calls do.

## Why the collector

It is the one place that sees both halves. `TelemetryCollector` already wraps every adapter —
`create_llm_adapter` puts it there for `sw implement`, both `sw review` paths, drift checking and
the API — and already computes each call's cost. Nothing else in the stack has both the running
total and the chance to refuse. Putting the check in the handlers instead would leave each new
call site to remember.

Cost is known only after a call returns, so the breaker cannot stop the request that crosses the
line. It stops the next one. That is the correct bound for a runaway loop, which is the threat.

## Two ceilings, because one has a hole

`estimate_cost` returns `0.0` for any model absent from the cost table. It logs a warning and
carries on, so a dollar ceiling alone accrues nothing for such a model and never trips —
configuring a model name the table does not know would be an unbounded run, which is exactly the
failure this capability exists to stop.

Token counts come back on every response and need no price list. `max_tokens_per_run` bounds the
case `max_spend_usd` cannot.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Spend is measured as it accrues | System | Accumulates cost and tokens per completed call against the run's ceilings | The running total is a fact the breaker can act on, not a number reconstructed from logs afterwards |
| FR-2 | A spent run sends nothing more | System | Checks the budget before `generate`, `generate_with_tools` and `generate_stream`, and refuses rather than calling the adapter | The loop stops at the ceiling instead of at whatever the provider or the operator's patience ends first |
| FR-3 | The refusal reaches the operator | System | Raises `BudgetExceededError`, which `Reviewer` re-raises instead of converting to a verdict | The run fails saying *you have spent your budget*, not "review failed" or "plan generation failed after 3 attempts" |
| FR-4 | A long run can be saved before the ceiling | System | Logs one warning at 80% of a ceiling, and only one | The operator can raise the limit while the work still has somewhere to go; after the trip it is too late |
| FR-5 | The ceilings are configuration, and on by default | System | Reads `llm.max_spend_usd` and `llm.max_tokens_per_run`, both finite by default, each disableable with `null` | A default install is protected; a deliberate `null` opts out; a mistyped `0` refuses everything rather than allowing everything |

Proof is by citation in the test files, read by `check_fr_coverage.py`. Each FR is behind a killed
mutant: neutering `check()`, tripping at zero, dropping the cost feedback, removing the check from
the tool path, letting `Reviewer` swallow the error again, and shipping either ceiling disabled all
fail the tests that claim them.

## What the research corrected

The plan assumed three callers would swallow the breaker, because each wraps an LLM call in
`except Exception`. Measured against the code, **two of the three do not**: in `Planner` and
`ScenarioGenerator` the LLM call sits *outside* the retry loop's `try`, which only covers JSON
parsing and model validation. A raising adapter has never been retried there.

Only `Reviewer._execute_review` genuinely wraps the call, and it converted every exception into
`ReviewVerdict.ERROR` — a verdict that reads as *the review found problems*. That is the one place
changed. The tests for the other two remain, because "the call is outside the `try`" is a property
worth pinning: moving it inside would silently make the breaker retryable.

## Non-Functional Requirements

| # | NFR | Requirement |
|---|-----|-------------|
| NFR-1 | Fail closed | A ceiling of `0` refuses everything. Disabling is `null` and nothing else, so a mistyped limit cannot open the gate |
| NFR-2 | Scope | One budget per `TelemetryCollector`, which `create_llm_adapter` builds once per CLI invocation or API request — so the ceiling is per run, which is the unit a loop runs away in |

`NFR-3` ("two additions and two comparisons per call") was deleted rather than marked. It was
an implementation note wearing a requirement's clothes: nothing about the product changes if it
is false, so there was no claim to prove.

## Non-Goals

- Per-step or per-project cumulative ceilings. The run is the unit that runs away.
- Enforcing spend against the persisted `llm_usage_log`. The breaker must work before a flush, and
  a run that never flushes is exactly the one that crashed while spending.
- Changing pricing or the cost table. The token ceiling exists precisely so this capability does
  not depend on the table being complete.
