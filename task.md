# INT-US-04 SF-01 — CB-3: restore feedback on resume

**FR-3** — a resumed run regenerates against the same findings a same-session run would have seen.
**Tier**: integration (the seam). CB-1 `e400cfdb`, CB-2 `3e8c29f9`.

## The defect

`context.feedback` is an in-memory field (`run_context.py:157`). `rehydrate_from_records` rebuilds
`plan_context` and nothing else, so a resumed run regenerates with no findings and repeats the
mistake validation caught.

The data is already persisted — `TECH-021` retains the failing step's `result` on loop-back
(`gates.py:222-223`). Only the replay is missing.

## Tasks

- [x] **T6** — `replay_feedback(pipeline, run, context)` in `hydration.py`, called from
      `rehydrate_from_records`.
      - test: `tests/integration/core/flow/engine/test_feedback_replay_across_resume.py` `[NEW]`
      - unit boundaries: `tests/unit/core/flow/engine/test_feedback_replay.py` `[NEW]`

## The replay condition (plan RB-4 — a conjunction, not one flag)

For a candidate source step at index *i*, all three must hold:

1. its gate is `on_fail=LOOP_BACK` and `loop_target` names the step at `run.current_step`;
2. the **target** record is `PENDING` with `result=None` (`gates.py:232-233` resets it);
3. the **source** record has a `result` whose status is **not** `PASSED` — checkable only because
   `TECH-021` stopped discarding it.

Two gates may share a target: **highest index wins**, the same rule `rehydrate_from_records`
already uses (`test_runner_rehydration.py::test_later_index_wins`).

Feedback is written under the **target** step's name — that is what `generation.py:87` pops
(`context.feedback.pop(step.name)`). Writing it under the source's name produces a dict nothing
reads while every "feedback was restored" assertion still passes, so the test asserts the
**consuming handler** sees it.

Reuses `GateEvaluator.inject_feedback` rather than re-implementing the shape (`gates.py` imports
only models and state — no cycle). Serialization needs nothing extra: the payload comes from an
already-persisted `result.output`, so it has been through the store's `default=str` once already.

## Red/Blue on this task list

| # | Finding | State |
|---|---|---|
| RD-1 | Does a resumed run actually land on the target index? | **cleared** — `gates.py:234` sets `run.current_step = target_idx`, and `current_step` is persisted |
| RD-2 | A run **parked** at the target (HITL) also has a target awaiting execution | **cleared** — a parked record is `WAITING_FOR_INPUT`, not `PENDING`, so condition 2 excludes it |
| RD-3 | `on_fail=RETRY` re-runs a step without ever injecting feedback | condition 1 matches `LOOP_BACK` only — pinned by test |
| RD-4 | Pipeline edited between sessions → index/name drift | mirror `rehydrate_from_records`' name guard; skip and warn |
| RD-5 | Import cycle if the replay reuses `inject_feedback` | **cleared** — `gates.py` imports only `engine.models` and `engine.state` |
| RD-6 | Ordering vs. the plan-hydration loop | independent; runs once after it |

## Adversarial test matrix

| Bucket | Test |
|---|---|
| **Happy path** | Loop-back, resume, and the regenerating handler **receives the findings** — asserted at the consumer, not on the dict |
| **Boundary/edge** | No loop-back → nothing replayed. Target already re-run (not `PENDING`) → nothing. Two gates sharing a target → highest index wins. Empty `step_records` → no-op |
| **Graceful degradation** | Source result present but `PASSED` → nothing replayed. Pipeline edited so names no longer line up → skipped with a WARNING, never raises |
| **Hostile/wrong input** | `current_step` out of range, and a `loop_target` naming a step that no longer exists → no crash, no replay |

## Commit boundary

CB-3 of 4. **Done when** deleting the `replay_feedback` call from `rehydrate_from_records` turns the
integration test **red** — the entire defect is an absent call, so a test that survives its removal
proves nothing. Plus `tests.py cb INT-US-04 --all`, pre-commit gate, HITL.
