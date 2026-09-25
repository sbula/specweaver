# INT-US-21 SF-01 CB-3 — Walkthrough: Cross-Session Rehydration (FR-3)

**Commit boundary:** 3 of 4 (`6811a943`; CB-1 `f1de38f1`, CB-2 `c4c1a109`) · **Date:** 2026-07-25 ·
Plan: [sf01](INT-US-21_sf01_implementation_plan.md) (APPROVED 2026-07-25)

## Delivered

`resume()` rebuilds the plan context from **persisted step records** before the loop starts, by
replaying the same `hydrate_plan_context` the live path uses — the two paths cannot drift.

| File | Change |
|---|---|
| `core/flow/engine/hydration.py` | **+`rehydrate_from_records()`** — replays persisted records through the live hook |
| `core/flow/engine/runner.py` | `resume()` rehydrates before `execute_run` |
| `docs/architecture/.../domain_flow_engine.md` | New "Cross-session rehydration" subsection |
| `tests/unit/core/flow/engine/test_runner_rehydration.py` | **NEW** — 19 unit tests |
| `tests/integration/core/flow/engine/test_rehydration_integration.py` | **NEW** — 8 integration tests |

- **Keyed on `record.result.status`**, not the record status: a gate-parked step's record is
  `WAITING_FOR_INPUT` while its stored result is `PASSED` (design R/B R2).
- **Paired by index AND name**: a YAML reordered or renamed between sessions keeps its length, so
  index alone would hydrate the wrong field.
- **Whole-run mismatch warns once.** The caller picks the `PipelineDefinition` to resume with — the
  REST path (`api/v1/pipelines.py`) resolves it independently of the CLI — so a single up-front
  warning names both pipelines. Advisory: same-named steps still rehydrate.

## Proof

| Suite | Result |
|---|---|
| Unit | **4940 passed**, 15 skipped |
| Integration | **523 passed**, 3 skipped, 15 deselected |
| E2E | **166 passed**, 1 skipped |
| **Grand total** | **5629 passed, 19 skipped** (CB-2: 5603; +26) |

`ruff` ✅ · `mypy` ✅ (305 files) · `C901` ✅ · file sizes ✅ 0 errors · `tach` ✅ · roadmap sync ✅.

The 8 integration tests pin what the in-memory unit tests cannot — `save_run → SQLite → load_run`
(a regression in `StateStore._row_to_run` or the schema would break every resumed run):

- `StepResult.output` survives a real SQLite round trip, with the gate-park shape (record
  `WAITING_FOR_INPUT` + result `PASSED`)
- `proposed_dal` survives intact (FR-7)
- two real runner sessions, two contexts, one store: the resumed handler sees the plan **on entry**
- `context.plan` rehydrated from the real `_plan.yaml` a previous session left
- artifact deleted between sessions → resume continues, only that field unset (NFR-2)
- pipeline YAML renamed between sessions → mismatch skipped, run resumes
- records `[PASSED, FAILED]` replay to `None` (stale-plan guard)
- the bundled `feature_decomposition.yaml` across sessions

A "wiring test" in `tests/unit/` that used a real `StateStore` and `PipelineRunner` was moved to its
proper integration counterpart (added after the user's Phase-2 challenge). Phase 7.5 Red/Blue: 1
finding (the whole-run warning), fixed.
