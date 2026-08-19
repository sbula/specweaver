# B-FLOW-05 — Token-Burn Circuit Breakers

**FRs owned: FR-1, FR-2, FR-3, FR-4, FR-5.** One budget object, one seam and one propagation fix;
splitting them across sub-features would be fiction. Proof and mutants are tabulated in
`B-FLOW-05_design.md`.

## Approach

`infrastructure/llm/budget.py` is new and pure: `SpendBudget` accumulates cost and tokens and
raises `BudgetExceededError` from `check()`. It has no I/O, no clock and no provider knowledge, so
it is testable without an adapter.

`TelemetryCollector` gains the budget. `check()` runs at the head of all three generation methods;
`_capture` feeds the measured cost and tokens back. `create_llm_adapter` builds the budget from
`LLMSettings`, which is the only place a collector is constructed.

`Reviewer._execute_review` re-raises `BudgetExceededError` ahead of its `except Exception`.

## Order

Tests first, red before the code, per `ADR-005`.

1. `tests/unit/infrastructure/llm/test_spend_budget.py` — the budget alone, each requirement
   beside its control: below the ceiling does not trip, a clean check is silent, a warning does
   not repeat.
2. `budget.py` until green.
3. `tests/unit/infrastructure/llm/test_collector_circuit_breaker.py` — all three generation paths
   tested separately. The tool path is the expensive one and a check on `generate` alone would
   leave it open with every test still passing.
4. The collector change.
5. `tests/unit/workflows/test_budget_error_propagates.py` — the breaker survives the retry loops.
6. `Reviewer` re-raise.
7. `tests/unit/infrastructure/llm/test_budget_from_settings.py` — defaults are finite, both
   ceilings configurable, and the collector actually carries what was configured.
8. Settings fields, factory wiring, `tach.toml` expose list.
9. Mutation pass: neuter `check()`, trip at zero, drop the cost feedback, drop the tool-path
   check, let `Reviewer` swallow it, ship each ceiling disabled.

## Non-Goals

- Per-step or per-project ceilings.
- Reading spend back from `llm_usage_log`.
- Touching the cost table.
