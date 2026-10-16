# C-FLOW-01 — Cost Telemetry

**Status**: APPROVED by the user 2026-10-15 — backfilled for a repair; the capability is `🔧` until the repair is
proven and signed off `[agreed 2026-10-15]`. · **Feature ID**: C-FLOW-01 (Legacy 3.12) · **DAL**: C
· **Plan of 2026-03**: [C-FLOW-01_implementation_plan.md](C-FLOW-01_implementation_plan.md)

| | |
|---|---|
| Stories | `US-16` (base journey, `INT-US-16`) · `US-04` paths L1, L3 (step limits, cost history) |
| Consumes | `C-FLOW-13` prices and the resolver · `B-FLOW-05` the brake's worst case per call |
| Enables | `sw usage` · `sw costs` · `B-FLOW-07` step limits · `D-UI-06` · `A-FLOW-01` |
| Not touched | prices and currency (`C-FLOW-13`) · the brake's limits (`B-FLOW-05`) · choosing models (`A-FLOW-01`) |

## Feature Overview

C-FLOW-01 records what every model call cost and which task it served, so spend is seen rather
than guessed. Each call is one row in `llm_usage_log`. The roadmap's done-when — *every call lands
in the ledger attributed to a task type* — was false when this design was written: a failed call
was never written, and every row of a run waited in memory until the run ended, so a killed run
lost them all. REST also wrote each run's rows a second time, which hid either writer's loss from
any test.

## Research Findings

| Fact (2026-10-15) | Where |
|---|---|
| Every model call runs inside a `PipelineRunner` run: `sw run`, `sw review`, `sw implement`, `sw standards`, drift, REST | the six `command_router`/`api_router` callers |
| One `TelemetryCollector` per server wraps every adapter; a tool loop is one row | `infrastructure/llm/resolve.py:211`, `collector.py:144` |
| Rows are buffered and written once, in the runner's `finally`; REST writes them again | `core/flow/engine/telemetry.py:21`, `interfaces/api/v1/_llm.py:77` |
| A failed call reaches the brake's totals and never the ledger | `collector.py:105 _record_failure` |
| A failed write is logged and dropped with the process | `collector.py:252-306` |
| The resolver holds the database (it reads step limits from it) | `resolve.py:64 history` |
| The cost tables change through idempotent column adds in `db_bootstrap.py`, never Alembic | `core/config/bootstrap/db_bootstrap.py:57-71` |
| Readers: `sw usage` (by task and model), `sw costs` (by model and server, month to date), step limits (passed steps only, joined to `llm_step_outcome`) | `infrastructure/llm/store.py:79,135,153` |

## Paths

| # | Path | Crosses |
|---|---|---|
| P1 | a CLI run's call → a `pending` row before the request, `ok` with its real numbers after | `D-FLOW-01` runner |
| P2 | a REST call → the same, once | `interfaces.api` |
| P3 | a call that fails → its row `failed`, with the usage the provider reported or *tokens unknown* | `B-FLOW-05` brake |
| P4 | a run killed during a call → its row stays `pending`; `sw usage` shows it as not finished, at most the worst case | `infrastructure.llm` |
| P5 | the ledger cannot be written → the run goes on; `sw run` ends saying how many calls are missing | `core.flow.interfaces` |
| P6 | `sw usage`, `sw costs` → failed calls in the totals and on their own line; interrupted ones apart | `infrastructure.llm` |
| P7 | step limits read the history → `ok` and `failed` rows of passed steps count, `pending` ones never | `B-FLOW-07` (`US-04` L1) |
| P8 | `sw implement` → `sw usage` still shows the run's tokens and cost | `INT-US-16` FR-1 |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Every request is in the ledger | Collector | SHALL write one row for every model request — CLI, REST and pipeline alike — naming the project's registered name, task type, model, server, run, step and DAL | spend is seen, not guessed |
| FR-2 | Written as it happens | Collector | SHALL write the row as `pending`, with the brake's worst case, before the request is sent, and SHALL update it to `ok` or `failed` with the real numbers when the call ends `[agreed 2026-10-15]` | a killed process loses no row |
| FR-3 | Failed calls count | Collector | SHALL mark a call that raised `failed`, with the usage the provider reported, else *tokens unknown*, and with its duration and step `[agreed 2026-10-15]` | a billed failure is visible spend |
| FR-4 | One writer | Collector, runner, REST | The collector SHALL be the only writer of `llm_usage_log`; no end-of-run write remains `[agreed 2026-10-15]` | a lost write cannot hide behind a second one |
| FR-5 | A missing row is told | Collector, run summary | A write that fails SHALL never stop the run; the end of `sw run` SHALL say how many calls could not be written `[agreed 2026-10-15]` | a gap in the ledger is never silent |
| FR-6 | Failures and interruptions are shown | `sw usage`, `sw costs` | SHALL count `failed` rows in the totals and show them on their own line — *of which failed: N calls, X*; a `pending` row SHALL show as *not finished (running now, or the process was killed): N calls, at most X*, outside the totals — the usage commands do not read the run store `[agreed 2026-10-15]` | the person sees why spend rose |
| FR-7 | History reads real spend | Step limits | SHALL count `ok` and `failed` rows of passed steps and never `pending` ones | a limit is never set from a guess |
| FR-8 | The status column | Store | `llm_usage_log.call_status` SHALL hold `pending`, `ok` or `failed`, added like the other history columns; rows from before get `ok` `[agreed 2026-10-15]` | the status is queryable, not encoded in another field |

`call_status` says whether the call technically worked — never how good its result was. A quality
score per call or task is `A-FLOW-01`'s: who ranks it, by which criteria, on which scale is open
there `[agreed 2026-10-15]`.

## Requirement–Surface Bindings

| FR | Binds to | Verified how |
|---|---|---|
| FR-1, FR-2, FR-3 | `TelemetryCollector.generate`, `.generate_with_tools`, `.generate_stream`; `create_usage_record(...)`; `_reserve` → the brake's worst case | read `infrastructure/llm/collector.py:81-232` |
| FR-2, FR-4 | the database the resolver already holds (`RoleResolver(..., history=db)`) | read `infrastructure/llm/resolve.py:64,211` |
| FR-4 | the runner's `_flush_telemetry` and REST's `run_steps` flush, both removed | read `core/flow/engine/runner.py:333`, `interfaces/api/v1/_llm.py:75` |
| FR-5 | `show_run_summary(final_run)` | read `core/flow/interfaces/run_summary.py` |
| FR-6 | `LlmRepository.get_usage_summary`, `.get_usage_by_task_type`, the `sw costs` query | read `infrastructure/llm/store.py:135-200`; `infrastructure.llm.interfaces` may not depend on `core.flow` (`tach.toml`) |
| FR-7 | `step_history_limit` | read `infrastructure/llm/store.py:65-100` |
| FR-8 | `_add_history_columns` | read `core/config/bootstrap/db_bootstrap.py:57-71` |

## Non-Functional Requirements

| # | NFR | Rule |
|---|---|---|
| NFR-1 | Telemetry never breaks the run | Carried from `INT-US-16` NFR-1: a write failure is logged and swallowed, never propagated |
| NFR-2 | What is kept | No prompt or response text is stored; rows are kept without a time limit `[agreed 2026-10-15]` |
| NFR-3 | Unknown stays unknown | An unknown price is stored as unknown, never 0 (`C-FLOW-13` FR-12) |

## Architectural Decisions

| # | Decision | Why | Switch? |
|---|---|---|---|
| AD-1 | The collector writes its own rows, through the database the resolver holds `[agreed 2026-10-15]` | one home per fact; a killed run keeps its rows | Yes — the end-of-run write `INT-US-16` documents goes |
| AD-2 | `call_status` is technical, apart from any quality score `[agreed 2026-10-15]` | a future ranking needs its own name and owner | No |

`INT-US-16` (finished) binds its FR-1 to "the flush that writes them at run end". Its promise — the
run's usage is persisted and `sw usage` shows it — still holds and now also holds for a killed run;
that binding sentence is superseded here, and its mutant corpus is re-pointed to the collector's
write, not deleted.

## Sub-Feature Breakdown

| SF | Does | FRs | Depends on |
|---|---|---|---|
| SF-01 | The write: `pending` before, `ok`/`failed` after, one writer, the column ([plan](C-FLOW-01_sf01_implementation_plan.md)) | FR-1, FR-2, FR-3, FR-4, FR-8 | — |
| SF-02 | The readers: the run summary's missing count, `sw usage`/`sw costs` lines, step history | FR-5, FR-6, FR-7 | SF-01 |

## Execution Order

SF-01, then SF-02.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | The write | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | The readers | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Now**: SF-01 committed — every call is in the ledger from the moment it is sent; the collector is its only writer.
**Next**: the implementation-plan skill for SF-02 (the readers).
