# Implementation Plan: Cost Telemetry [SF-01: The write]
- **Feature ID**: C-FLOW-01
- **Sub-Feature**: SF-01 — The write
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-01/C-FLOW-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-01/C-FLOW-01_sf01_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-16

**FRs owned**: FR-1, FR-2, FR-3, FR-4, FR-8 · **Depends on**: none · **Paths**: P1, P2, P3, P4, P8

## Goal

Every request is in the ledger the moment it is sent, and stays there whatever happens next:
`pending` before the request, `ok` or `failed` after it, written by the collector alone.

## Shape

| Piece | Where | Tag |
|---|---|---|
| `call_status` column, added like the history columns; rows from before get `ok` | `core/config/bootstrap/db_bootstrap.py`, `infrastructure/llm/store.py` (`LlmUsageLog`) | MODIFY |
| `open_call(record) -> id` writes the `pending` row; `close_call(id, record, status)` sets the real numbers | `infrastructure/llm/store.py` (`LlmRepository`) | MODIFY |
| the collector takes the ledger (the database the resolver already holds); each path opens the row after the brake allowed the call and before the request, and closes it after | `infrastructure/llm/collector.py`, `infrastructure/llm/resolve.py` | MODIFY |
| a tool loop's `pending` row carries the worst case of every round so far | `collector.py` (`before_request`) | MODIFY |
| a write that fails is logged, never raised, and counted: `unwritten` on the collector, summed by the router | `collector.py`, `infrastructure/llm/router.py` | MODIFY |
| the buffer, `flush`, `flush_async` and `records` go; the runner keeps writing step outcomes only; REST's write goes | `collector.py`, `core/flow/engine/telemetry.py`, `interfaces/api/v1/_llm.py` | MODIFY |

Order inside one call: the brake's check (a refused call is never sent, so it gets no row) → open the
`pending` row with the worst case → send → close it `ok` with the response's usage, or `failed`
with the usage the error carries, else *tokens unknown* (tokens left at 0, cost unknown).

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the column and the two repository writes | FR-8 | an older ledger gets no `call_status`, and there is no way to write a `pending` row — red today |
| CB-2 | the collector writes; one writer; the count of failed writes; `INT-US-16`'s corpus re-pointed | FR-1, FR-2, FR-3, FR-4 | a call is not in the ledger while it runs, a failed call never is, and REST writes every row through a second path — red today |

| CB | Tier | Test |
|---|---|---|
| CB-1 | integration | a real SQLite ledger built the old way gains the column, keeps every row as `ok`, and a second start changes nothing |
| CB-2 | integration + e2e | a real collector over a real ledger, with a provider double that looks at the ledger mid-call; `sw implement` and `POST /implement` leave exactly one row per call; a broken ledger leaves the run green and the count right |

## Mutants

| id | Line neutralised | Must kill |
|---|---|---|
| `old-rows-not-ok` | the column's default | CB-1 |
| `pending-not-written` | the row opened before the request | CB-2 |
| `failed-not-marked` | the `failed` close of a call that raised | CB-2 |
| `round-worst-not-raised` | the tool loop's worst-case update | CB-2 |
| `write-failure-uncounted` | the `unwritten` count | CB-2 |
| `telemetry-wrap-never-applied` | `INT-US-16`'s, kept as it is | CB-2 |
| `flush-becomes-a-no-op` | `INT-US-16`'s, re-pointed to the collector's open | CB-2 |

## Research Notes

- `TelemetryCollector(adapter, project, prices, budget, scope_of, redactor, server)` buffers
  `UsageRecord`s in `_records` and writes them in `flush`/`flush_async` (`collector.py:56-306`).
- `_reserve(messages, config) -> (scope, Reservation)` runs the brake before every request;
  `_worst_of` gives the worst-case `Cost(usd, tokens)` (`collector.py:87-103`).
- A raised call goes to `_record_failure`, which reads `exc.usage` when the adapter attached it
  (`collector.py:105`).
- `RoleResolver(..., history=db)` holds the database; `_adapter` builds one collector per server
  (`resolve.py:64,211`).
- `flush_telemetry` writes every collector's buffer, then `record_step_outcomes`
  (`core/flow/engine/telemetry.py:21`); REST writes again in `run_steps` (`interfaces/api/v1/_llm.py:77`).
- `LlmRepository.log_usage(record)` adds one `LlmUsageLog` (`infrastructure/llm/store.py:112`);
  `_add_history_columns` is the pattern for an added column (`db_bootstrap.py:57`).
- Tests built on the buffer: `tests/unit/infrastructure/llm/test_collector.py` (flush cases),
  `tests/integration/test_telemetry_roundtrip.py`, `tests/integration/test_telemetry_integration.py`,
  `tests/unit/interfaces/api/v1/test_telemetry_wiring.py` (two flush cases). They are rewritten
  against the ledger, or removed where they only tested the buffer.
- `INT-US-16_mutants.json`: `flush-becomes-a-no-op` anchors `collector.flush(db)` in
  `flush_telemetry`; `telemetry-wrap-never-applied` anchors the collector's construction.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| — | none open: the design settled every trigger `[agreed 2026-10-15]` | — |

## Backlog

none
