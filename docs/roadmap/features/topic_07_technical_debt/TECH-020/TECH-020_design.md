# Design: Extract the Step-Execution Loop from PipelineRunner

- **Feature ID**: TECH-020
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-12 — see §Delivery. Both candidate approaches taken; the
  `# noqa: C901` is **removed, not relocated**.
- **Origin**: INT-US-21 SF-03 CB-2 pre-commit gate, finding A5 (2026-07-27)

## Problem Statement

`src/specweaver/core/flow/engine/runner.py` is **exactly 600 lines against a 600-line RED
threshold**. The next line added to it blocks the commit that adds it, whatever that commit is
about.

That already happened once. CB-2 added a one-line `current_run_id` accessor; the file hit 601 and
the gate blocked. The fix was to condense the *comment* explaining the accessor — the right call in
the moment, but it means the file's headroom is now bought with prose density rather than
structure, and the next contributor pays with no warning.

The real measurement is worse than the line count suggests:

| | |
|---|---|
| `runner.py` | 600 lines |
| **`_execute_loop`** | **lines 215–575 — 360 lines in ONE method** |
| its complexity | suppressed with `# noqa: C901` |
| everything else | `__init__`, `current_run_id`, `run`, `resume`, and five 5-line helpers |

So ~60% of the file is a single method whose complexity warning is silenced. The C901 suppression
is the load-bearing part of this ticket: the file-size threshold is a proxy, but the `noqa` is a
direct admission that the method is past the project's own complexity bar.

Three modules have already been extracted from this file during INT-US-21 —
`engine/hydration.py`, `engine/approval.py`, `engine/staleness.py` — each time because a feature
needed the room. That is three data points saying the loop, not the file, is the thing that needs
splitting.

## Candidate Approaches (not yet designed)

- Extract the per-step execution body (handler lookup → execute → hydrate → gate → route) into a
  collaborator, leaving `_execute_loop` as the iteration and bookkeeping. The seams are already
  visible: SF-01 pulled hydration, approval and staleness out of exactly this loop.
- Separate the *loop-back / retry* bookkeeping from step execution. `attempts` handling is one of
  the loop's distinct responsibilities and is where `NFR-2`'s inherited per-session reset lives
  (`attempts` re-initialises on every `_execute_loop` entry, so a resumed run gets a fresh 3
  strikes — documented, unfixed, and easier to reason about once separated).
- Whatever the split, the `# noqa: C901` must be **removed, not relocated**. A suppression that
  survives the refactor means the refactor did not happen.

## Non-Goals (proposed, pending design)

- No behaviour change. This is structural; every existing test must pass untouched, and the
  handover/telemetry `finally:` contract must be preserved exactly (`TECH-017` already flags
  graceful shutdown as under-tested — do not disturb it blind).
- Not a rewrite of the gate/router evaluation, which live in their own modules already.
- Not bundled into a feature commit. Same rule as `TECH-016`: its own commits, so a behaviour
  regression is bisectable to a structural change rather than hidden inside a feature.

## Delivery, 2026-08-12

### It blocked a real change first

The ticket predicted "the next line added to it blocks the commit that adds it, whatever that
commit is about." That happened again on 2026-08-12: `TECH-014`'s **one-line** fan-out isolation
call pushed the file to 601 and the gate refused it. The workaround was to move that fix's
rationale into a helper's docstring — structural rather than the comment-condensing this ticket
names — leaving the file at 599 of 600. Second recorded data point, and the trigger for doing this.

### What moved

New `engine/step_execution.py` (459 lines, **100% statement and branch coverage**), following the
convention the three earlier extractions from this loop established: free functions taking the
runner first, so `_persist` / `_log` / `_emit` stay the runner's concern.

| | before | after |
|---|---|---|
| `runner.py` | 599 lines | **292** |
| `_execute_loop` | 365 lines | **21** |
| cognitive complexity | **50** (ceiling 15) | below ceiling — absent from the complexipy report |
| McCabe | over 10, suppressed | under 10, **suppression deleted** |

Both candidate approaches were taken, not one:

- **The per-step body became a collaborator.** `run_one_step` is the whole iteration — approve,
  dispatch, execute, judge, advance — leaving `_execute_loop` as iteration and bookkeeping exactly
  as proposed. An intermediate version that only extracted the gate and router blocks still scored
  McCabe 13; going the whole way was what actually cleared the bar.
- **Loop-back/retry bookkeeping separated.** `attempts`, `route_jumps` and the one-shot
  `approve_parked` now live in a `LoopState` dataclass rather than as three loop-locals threaded
  through tuple returns.

The one duplication collapsed rather than moved is `fail_run`: four sites (missing handler, gate
`stop`, ungated failure, router error) open-coded an identical persist → log → emit `step_failed` →
emit `run_failed` sequence. That is why the loop shrank instead of merely relocating.

`LoopAction` distinguishes `CONTINUE` (re-enter **without** advancing `current_step` — retry and
loop-back both depend on it) from `PROCEED` (fall through to advance/route). The distinction is
real only inside `run_one_step`; to `_execute_loop` both simply mean "next iteration", which is
what let the loop collapse to a single `is LoopAction.RETURN` check.

### No behaviour change, and how that was held to

Every existing test passes **untouched** — 6435 in the full suite, zero modified. That was
affordable because the loop already had **44 branches at zero partial coverage** before the
refactor started; the safety net was measured first, not assumed. The extracted module inherits it
at 100%.

Two faithfulness slips were caught and corrected mid-refactor rather than shipped:

- `execute_step` was first written with the context-injection and the handler call in **separate**
  `try` blocks. The original wraps both in one. Restored — a refactor that "obviously" preserves
  behaviour is exactly where that assumption goes unexamined.
- `ruff --fix` deleted `resolve_should_isolate` from `runner.py` once its last call site moved,
  breaking tests that import it from there. It is now an explicit `__all__` re-export with a
  comment, since the contract is that tests do not change.

`mypy` surfaced that `apply_gate` had an unstated precondition (its caller had already checked
`step_def.gate is not None`). The gate is now a typed parameter, so the requirement is in the
signature rather than an obligation on the reader.

### Deliberately not fixed

`NFR-2`'s inherited per-session `attempts` reset. `LoopState` is still constructed fresh on every
`_execute_loop` entry, so a resumed run still gets a fresh three strikes. The ticket predicted this
would be "easier to reason about once separated" — it is, and it is now one field with one
construction site instead of a loop-local. Changing it would be a behaviour change, which this
ticket forbids. **Minted as `TECH-033` on 2026-08-12**, which also corrects the two false reasons `INT-US-21`'s NFR-2 gave for parking it.

## Next Step

Done. `C-FLOW-12`'s fan-out work no longer pays this tax.

Related: `TECH-015` (retire grab-bag modules) shares the "structure follows pressure" theme;
`TECH-017` covers the graceful-shutdown coverage gap that makes this refactor riskier than it looks.
