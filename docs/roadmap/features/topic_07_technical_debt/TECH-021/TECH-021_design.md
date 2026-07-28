# Design: loop_back Discards the Failing Step's Result

- **Feature ID**: TECH-021
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: INT-US-21 SF-03 CB-3 e2e (2026-07-28) — found by the first test to drive a bundled
  pipeline through a HITL gate

## Problem Statement

When a gate's `on_fail: loop_back` fires, the failing step's **result is discarded**. The record is
left `status=running, result=None`, so the reason the step failed is never persisted and never
shown.

Measured on the bundled `feature_decomposition` journey with a spec that fails the battery
(4 FAILs: S06, S07, S09, S10):

```
SESSION 1  parked at draft_feature    validate_feature: pending,  result=None
SESSION 2  approve -> validate_feature FAILS -> loop_back -> parked at draft_feature
           validate_feature: status=running, attempt=1, result=None
SESSION 3  identical
SESSION 4  identical
```

The user experience is the defect: they are parked at the **draft** gate, with nothing anywhere
telling them their spec failed validation or which rules failed. They approve again, it fails
again, and they land in the same place. The journey is stable but gives no purchase — every resume
looks like the first one.

This is engine-wide `loop_back` behaviour, not specific to `feature_decomposition`. Any pipeline
with `on_fail: loop_back` loses its failure diagnostics the same way, which is why this is a `TECH`
ticket rather than a fix inside INT-US-21.

**Separately and already delegated:** the 3-strike budget never bites across sessions, because
`_execute_loop` re-initialises `attempts` on every entry (`runner.py`), so each `sw run --resume`
grants a fresh budget. INT-US-21's `NFR-2` records that as an inherited limit and delegates it to
`C-FLOW-07` (persisting attempt counters is a state-schema change). **Do not fix that here** — but
note the two compound: an unbounded loop whose failures are also invisible.

## Candidate Approaches (not yet designed)

- Persist the failing `StepResult` on the record before the loop_back rewinds, so the diagnostics
  survive. The record already has a `result` field; it is simply not written on this path.
- Surface the retained reason at the park. `_on_run_parked` currently prints only the step name and
  the resume hint (`display.py`) — the same limitation INT-US-21 hit for FR-7, where the fix was to
  put the text in the handler's own output and leave rendering to the CLI journey.
- Decide what `status` a looped-back step should carry. `running` is wrong — nothing is running.
  `failed` with a retained result reads correctly and is what a human would expect.

## Non-Goals (proposed, pending design)

- Not the attempts-reset (`C-FLOW-07`, via INT-US-21 `NFR-2`).
- Not a redesign of gate semantics — `loop_back` looping is correct; losing the evidence is not.
- Not bundled into a feature commit.

## Next Step

Run the `specweaver-design` skill. The failing case is already reproducible from
`tests/e2e/capabilities/workflows/test_int_us_21_decomposition_e2e.py`, where
`TestE8ValidationFailureLoopsBack::test_the_validation_failure_is_recorded_for_the_human` is a
**strict `xfail`** — it will start failing the moment this is fixed, which is the signal to remove
the marker.
