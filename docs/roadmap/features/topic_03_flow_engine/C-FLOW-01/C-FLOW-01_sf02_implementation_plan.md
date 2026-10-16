# Implementation Plan: Cost Telemetry [SF-02: The readers]
- **Feature ID**: C-FLOW-01
- **Sub-Feature**: SF-02 — The readers
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-01/C-FLOW-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-01/C-FLOW-01_sf02_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-16

**FRs owned**: FR-5, FR-6, FR-7 · **Depends on**: SF-01 (committed) · **Paths**: P4, P5, P6, P7

## Goal

What the ledger now holds is read honestly: a `pending` row is never counted as spend, a failed
call is counted and named, and every command that calls a model says when calls are missing.

## Shape

| Piece | Where | Tag |
|---|---|---|
| the three summary queries skip `pending` rows | `infrastructure/llm/store.py` (`get_usage_summary`, `get_usage_by_task_type`, `get_spend_by_server`) | MODIFY |
| `get_status_totals(project, since)` → per status (`failed`, `pending`): calls, tokens, known USD, calls with no price | `store.py` (`LlmRepository`) | NEW |
| step history skips `pending` rows; a step with a failed call whose tokens are unknown has no token total | `store.py` (`step_history_limit`) | MODIFY |
| `sw usage`: under the table, *of which failed: N calls, X* and *not finished (running now, or the process was killed): N calls, at most T tokens, X* | `infrastructure/llm/interfaces/cli.py` | MODIFY |
| `sw costs`: the same two lines after the models, this month only | `infrastructure/llm/interfaces/cli.py` | MODIFY |
| `unwritten` counts calls, not writes: a call whose row was never opened, or never closed | `infrastructure/llm/collector.py` | MODIFY |
| every CLI command that builds a router says at its end, on stderr: *N calls of this command are missing from the cost ledger or were not closed in it* | `infrastructure/llm/interfaces/command.py` (`command_router`, `optional_command_router`) | MODIFY |
| `POST /review` and `POST /implement` answer with `unwritten_calls` | `interfaces/api/v1/_llm.py`, `review.py`, `implement.py`, `schemas.py` | MODIFY |
| a run's end logs a warning with the count; the only report a background REST run can give | `core/flow/engine/telemetry.py` (`flush_telemetry`) | MODIFY |

The CLI line is registered once, in the two router builders, with `click.get_current_context(silent=True)
.call_on_close(...)`. It then runs at the end of every command that has a router — also on exit 1 and
exit 130 — and no command can forget it. It goes to stderr, so `sw run --json` stays clean NDJSON.
`click` comes with `typer`.

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the queries: no `pending` in totals; the status totals; step history | FR-6 (queries), FR-7 | a `pending` row adds its worst case to every total, and joins a passed step's history after a resume — red today |
| CB-2 | `sw usage` and `sw costs` show the failed and not-finished lines | FR-6 | neither command names a failed or a not-finished call — red today |
| CB-3 | the count of calls, the end-of-command line, the REST field, the run-end warning | FR-5 | a command whose ledger refuses writes ends silent; REST answers without the field — red today |

| CB | Tier | Test |
|---|---|---|
| CB-1 | integration | rows `ok`, `failed`, `pending` in a real ledger (`tests/ledger.Ledger`); each query read back; a killed then resumed run's `pending` row on a passed step leaves the limit as it was |
| CB-2 | e2e | `sw usage` and `sw costs` through the CLI over a seeded ledger; numbers asserted, never truncated strings |
| CB-3 | integration + e2e | the collector over a real ledger that refuses each write in turn (open, widen, close); `sw implement` with a refusing ledger ends with the line on stderr; `POST /implement` and `POST /review` carry `unwritten_calls` |

## Mutants

| id | Line neutralised | Must kill |
|---|---|---|
| `summary-counts-pending` | the `pending` filter of `get_usage_summary` | CB-1 |
| `spend-counts-pending` | the `pending` filter of `get_spend_by_server` | CB-1 |
| `history-counts-pending` | the `pending` filter of `step_history_limit` | CB-1 |
| `history-counts-unknown-tokens` | the token-unknown guard of `step_history_limit` | CB-1 |
| `failed-line-hidden` | the failed line | CB-2 |
| `unfinished-line-hidden` | the not-finished line | CB-2 |
| `usage-shows-no-status` | `sw usage` printing the two lines | CB-2 |
| `costs-shows-no-status` | `sw costs` printing the two lines | CB-2 |
| `widen-counted-as-missing` | the widen write counted in `unwritten` | CB-3 |
| `unwritten-never-told` | the `call_on_close` registration | CB-3 |
| `rest-unwritten-dropped` | `unwritten_calls` set from the router | CB-3 |

## Research Notes

- `sw costs` reads `_month_spend` → `get_spend_by_server(project, since)` and prints
  *this month X + N unknown* per `model@server` (`infrastructure/llm/interfaces/cli.py:48-81,182`).
- `sw usage` builds its table from `get_usage_summary(project, since)` (`cli.py:230-310`).
- `get_usage_by_task_type` has no caller in `src/`; two tests read it. It gets the same filter.
- `step_history_limit` joins `llm_step_outcome` (`passed` only), groups by run and step, and skips a
  step with an unpriced call when the unit is USD (`store.py:70-100`).
- SF-01's `_write` adds 1 to `unwritten` per failed write: a failed widen counts a call that is still
  written and closed, and a call can count twice (`collector.py:282-319`). `close_call` returning
  False (the row is gone) is not counted.
- Every CLI command gets its router from `command_router` or `optional_command_router`
  (`infrastructure/llm/interfaces/command.py`): `sw run`, `sw resume`, `sw review`, `sw implement`,
  `sw drift check`, `sw standards`. `_core.console` is stdout.
- REST: `/review` and `/implement` wait for their run (`run_steps`, `interfaces/api/v1/_llm.py:44`);
  `/pipelines/{name}/run` and `/runs/{id}/resume` answer before the run ends, so the count can only go
  to the server log. `/standards/scan` calls no model.
- `flush_telemetry(context, logger, run)` runs at every run's end and can read
  `context.model.llm_router` (`core/flow/engine/telemetry.py:21`).

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | Which commands say how many calls are missing | Every command that calls a model, one shared line; REST answers with `unwritten_calls` `[agreed 2026-10-16]` |
| Q2 | A failed call whose tokens are unknown, in token step history | Its step has no token total, as a step with an unpriced call has no USD total `[agreed 2026-10-16]` |

## Backlog

none
