# Walkthrough: INT-US-21 SF-01 CB-3 — Cross-Session Rehydration (FR-3)

- **Design**: `INT-US-21_design.md` (APPROVED 2026-07-25)
- **Plan**: `INT-US-21_sf01_implementation_plan.md` (APPROVED 2026-07-25)
- **Commit boundary**: 3 of 4 (CB-1 `f1de38f1`, CB-2 `c4c1a109`)
- **Date**: 2026-07-25

---

## What changed and why

CB-2 made the plan context work *within* a session. It does not survive a park: the fields live in
memory and die with the process. FR-3 rebuilds them from **persisted step records** on `resume()`,
before the loop starts, by replaying the same `hydrate_plan_context` the live path uses — so the
two paths cannot drift apart.

| File | Change |
|---|---|
| `core/flow/engine/hydration.py` | **+`rehydrate_from_records()`** — replays persisted records through the live hook |
| `core/flow/engine/runner.py` | `resume()` rehydrates before `execute_run` |
| `docs/architecture/.../domain_flow_engine.md` | New "Cross-session rehydration" subsection |
| `tests/unit/core/flow/engine/test_runner_rehydration.py` | **NEW** — 19 unit tests |
| `tests/integration/core/flow/engine/test_rehydration_integration.py` | **NEW** — 8 integration tests |

### The load-bearing subtlety

A **gate-parked** step's *record* status is `WAITING_FOR_INPUT` while its stored *result* status is
`PASSED`. Keying rehydration on the record status would silently skip exactly the step a resumed
run needs. The function keys on `record.result.status` (design R/B R2).

Pairing is by **index AND name**: a YAML reordered or renamed between sessions keeps the same
length, so index alone would pair a stored result with the wrong action/target and hydrate the
wrong field.

---

## Test results

| Suite | Result |
|---|---|
| Unit | **4940 passed**, 15 skipped |
| Integration | **523 passed**, 3 skipped, 15 deselected |
| E2E | **166 passed**, 1 skipped |
| **Grand total** | **5629 passed, 19 skipped** |

CB-2 baseline was 5603. Net **+26**.

## Quality gates

`ruff` ✅ · `mypy` ✅ (305 files) · `C901` ✅ · file sizes ✅ 0 errors · `tach` ✅ · roadmap sync ✅.

---

## HITL gate decisions

| Gate | Findings presented | User decision |
|---|---|---|
| **Phase 1** | No architecture findings — no new modules, imports or boundary surface | — |
| **Phase 2** | Coverage matrix + 1 proposed unit story. **I proposed zero integration tests.** | **User challenged: *"what about the integration tests?!?!?"*** |
| **Phase 2 (corrected)** | 8 integration tests proposed and implemented (below) | Implemented |
| **Phase 7.5** | Red/Blue on the diff: 1 finding, fixed | *presented at this commit gate* |

### The Phase-2 correction — what I got wrong

My first Phase-2 analysis marked the `resume()` call site **❌ under Integration in my own coverage
matrix**, then argued the gap away on the grounds that a "wiring test" already proved it end to end.
Two things were wrong with that:

1. **That test was in `tests/unit/`** while using a real `StateStore`, a real `PipelineRunner` and
   two real sessions. It was an integration test wearing a unit test's clothes — and the pre-commit
   guidance is explicit that the three levels are not interchangeable.
2. **It hid the one seam only an integration test can cover.** All 19 unit tests build `PipelineRun`
   objects **in memory**. FR-3's entire premise is *"rehydration reads ONLY persisted state"* — yet
   nothing exercised `save_run → SQLite → load_run`. A regression in `StateStore._row_to_run` or the
   schema would break every resumed run with the whole unit suite still green.

I verified the round trip is correct today (it is) — but correctness-now is not coverage. The
misplaced unit test was removed and replaced by its proper integration counterpart.

**The 8 integration tests now pin:**

- `StepResult.output` surviving a real SQLite round trip, and the gate-park shape
  (record `WAITING_FOR_INPUT` + result `PASSED`) surviving with it
- `proposed_dal` surviving intact — FR-7 depends on it reaching downstream consumers
- Two real runner sessions, two separate contexts, one store: the resumed handler observes the
  plan **on entry**
- `context.plan` rehydrated from the real `_plan.yaml` a previous session left on disk
- The artifact deleted between sessions → resume continues, only that field stays unset (NFR-2
  end-to-end, not with a fake path)
- The pipeline YAML renamed between sessions → mismatch skipped, run still resumes
- Cross-session mirror of the stale-plan guard: records `[PASSED, FAILED]` replay to `None`
- The bundled `feature_decomposition.yaml` driven across sessions

### Phase 7.5 Red/Blue — 1 finding, fixed

**Whole-run pipeline mismatch was only caught per-step.** The caller chooses which
`PipelineDefinition` to resume with, and nothing guarantees it produced the records — the REST
resume path (`api/v1/pipelines.py`) resolves the pipeline independently of the CLI path. Previously
a mismatch surfaced only as N per-step name warnings with no statement of the actual cause. Now a
single up-front warning names both pipelines. Advisory, not a hard stop: same-named steps still
rehydrate correctly.

---

## What CB-3 deliberately does NOT do

- **Does not make `sw resume` advance past a reviewed HITL gate.** That is CB-4 (FR-4); today a
  resumed run still re-executes the parked step and the gate re-parks. CB-3 only guarantees the
  plan context is correct when it does.
- No seam pins (FR-9 → SF-02), no CLI journey or e2e proof (FR-8/FR-10 → SF-03).
- US-21 remains 🟡; no roadmap checkbox moved.
