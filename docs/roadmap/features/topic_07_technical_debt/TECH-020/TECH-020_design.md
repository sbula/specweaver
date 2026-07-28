# Design: Extract the Step-Execution Loop from PipelineRunner

- **Feature ID**: TECH-020
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
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

## Next Step

Run the `specweaver-design` skill. Sequence **before** the next feature that needs to touch
`runner.py` — which, on current plans, is `C-FLOW-12`'s fan-out work. Landing it after that feature
means the feature pays the tax first.

Related: `TECH-015` (retire grab-bag modules) shares the "structure follows pressure" theme;
`TECH-017` covers the graceful-shutdown coverage gap that makes this refactor riskier than it looks.
