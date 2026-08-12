# Design: A Step's Retry Budget Resets on Every `sw resume`

- **Feature ID**: TECH-033
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Named as an accepted inherited limit in `INT-US-21`'s NFR-2 (2026-07-27), carried
  forward by `TECH-020` (2026-08-12) which made it structurally visible without changing it —
  behaviour change was forbidden there. Minted 2026-08-12 at the user's request.

## Problem Statement

`gate.max_retries` bounds how many times a failing step re-runs. The counter it is checked against
lives only in memory: `_execute_loop` builds a fresh `LoopState` on every entry
(`engine/runner.py:243`), whose `attempts: dict[int, int]` starts empty. `resume()` re-enters the
same loop, so **every `sw resume` grants the step a full, fresh budget**.

`max_retries: 3` therefore bounds retries *per session*, not per step. Across N resumes a step can
run 3N times, and the LLM spend that goes with it is bounded only by how many times a human types
`sw resume`.

Both consumers share the counter — `_handle_retry` and `_handle_loop_back` (`engine/gates.py`)
each increment `attempts[step_idx]` and compare it to the same `gate.max_retries` — so the reset
widens a `loop_back` budget exactly as it widens a `retry` one.

## Two claims in the existing record are wrong, and they are why this was never fixed

`INT-US-21`'s NFR-2 parks this with: *"Inherited, NOT fixed here (persisting attempt counters is a
state-schema change; `C-FLOW-07` territory)."* **Both halves are false**, measured 2026-08-12:

**1. It is not a state-schema change.** `StepRecord.attempt` already exists
(`engine/state.py`, `attempt: int = 1`, docstring *"Current attempt number (for future retry
tracking)"*), is already **written** by `_handle_retry` (`gates.py`, `record.attempt =
attempts[step_idx] + 1`), and already **round-trips through the store** — verified by saving a
`StepRecord(attempt=3)` and loading it back. The durable half of the mechanism is built and
working. What is missing is the **read**: nothing seeds `attempts` from the persisted value.

**2. `C-FLOW-07` would never have fixed it.** `C-FLOW-07` is **HITL Root-Cause Tagging** — a human
tagging *why* a pipeline failed, feeding the Friction Analytics attribution engine. It has nothing
to do with retry budgets. No capability anywhere in the roadmap covers retry-budget persistence, so
this defect was parked against a ticket that does not cover it and has been effectively orphaned
since. That is the reason it is a `TECH` ticket now and not a deferral: per the scope rules, a live
defect does not wait on an unbuilt capability — and here the capability would not have helped.

## Candidate Approaches (not yet designed)

- **Seed the counter from what is already persisted.** On loop entry, initialise
  `LoopState.attempts` from each `StepRecord.attempt` rather than from `{}`. Smallest possible
  change, uses the field the schema already carries, and needs no migration.
- **Close the write side first.** `_handle_loop_back` spends the budget but — unlike
  `_handle_retry` — never writes `record.attempt`, so the persisted counter is **already
  incomplete**. Seeding from it without fixing that would restore the budget for `retry` and
  silently keep resetting it for `loop_back`. This is a prerequisite, not an optional extra.

## Settled: this is a bug, not a documented behaviour

**Decided by the user, 2026-08-12.** `max_retries: 3` means **three attempts for that step, ever**.
A resume continues a run; it does not hand back a fresh budget. The per-session reset is a defect
in the counter's lifetime, not a design choice — it was never chosen, only observed and then
written down as a limitation.

This closes the one open question the ticket had, and it removes the "documented behaviour change"
reading entirely: the gate documentation does not need a new rule, because the rule it already
states is the correct one and the code does not honour it.

## Non-Goals (proposed, pending design)

- **Not** a change to `gate.max_retries`' default or to any pipeline YAML. The number is right;
  the counter's lifetime is wrong.
- **Not** token-spend budgeting — that is `B-FLOW-05` (Token-Burn Circuit Breakers). This ticket
  bounds *attempts*; a spend cap is a different mechanism and neither substitutes for the other.
- **Not** a rework of gate evaluation, which lives in `gates.py` and is out of scope beyond the
  two counter sites.

## Verification the design must specify

A test that **resumes** a run whose step has already spent its budget and asserts the step is not
re-run — the only shape that can catch this, since every existing retry test lives inside a single
`_execute_loop` entry and therefore cannot observe the reset. Plus a `loop_back` twin, because that
path's write side is the one that is missing.

## Next Step

Run the `specweaver-design` skill. The semantics question that would have gated it is **settled**
(see above), so the design's job is the sequencing: close `_handle_loop_back`'s missing write
first, then seed from the persisted counter, then prove it across an actual resume.

Related: `TECH-020` (which separated `attempts` into `LoopState` and made this a single field with
a single construction site); `INT-US-21` NFR-2 (the original record, corrected above).
