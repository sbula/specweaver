# Design: loop_back Discards the Failing Step's Result

- **Feature ID**: TECH-021
- **Epic**: Topic 07 (Technical Debt)
- **Status**: ✅ RESOLVED (2026-07-28) — fixed directly; the change was two lines and its proof already existed as a strict `xfail`
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
`tests/e2e/capabilities/workflows/test_feature_decomposition_e2e.py`, where
`TestE8ValidationFailureLoopsBack::test_the_validation_failure_is_recorded_for_the_human` is a
**strict `xfail`** — it will start failing the moment this is fixed, which is the signal to remove
the marker.

---

## Resolution (2026-07-28)

`_handle_loop_back` in `engine/gates.py` now records the failing step's status and result before it
rewinds:

```python
run.step_records[step_idx].status = result.status
run.step_records[step_idx].result = result
```

Placed in the gate evaluator rather than the runner deliberately — `runner.py` sits at its 600-line
RED threshold with zero headroom (`TECH-020`), and the evaluator already owns this kind of state
mutation (`park_current_step`).

**The strict `xfail` worked exactly as intended.** The moment the fix landed the test reported
`XPASS(strict)` and failed the suite, which is what signalled the marker could go. It is now an
ordinary passing test. That is the argument for `xfail(strict=True)` over deleting a test or
asserting the broken behaviour: the tripwire tells you when it is obsolete.

**Still open and NOT fixed here:** the retry budget does not accumulate across sessions —
`_execute_loop` re-initialises `attempts` on every entry, so each `sw run --resume` grants a fresh
3-strike allowance. That remains `C-FLOW-07`'s (via INT-US-21 `NFR-2`), unchanged.

## Carried down from the topic entry (2026-08-13, `TECH-044`)

Moved here verbatim when the entry was shortened to four lines — recorded rather than dropped.

- Measured on `feature_decomposition` with a spec failing 4 rules (S06, S07, S09, S10) — session 2
  approves the draft gate, `validate_feature` FAILS, the gate loops back, and the run parks at
  **draft** again with `validate_feature: status=running, result=None`.
