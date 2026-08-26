# Walkthrough: `TECH-049` `FR-11` — the test that was wrong for one minute a day

- **Ticket**: none, by the user's decision. *"I do not want a new tech ticket for that one but we
  must not forget it either! so just fix it!"* The record is this file, the test's own docstring,
  a new anti-pattern row, and two mutants now in the nightly corpus
- **Kind**: bugfix · **DAL-C** · 2026-08-26

## The failure

The nightly of `2026-08-26` (commit `7e4a4cc2`) ran red. The baseline named one test — which is
itself new, and is the `FR-3` fix from 2026-08-24 doing its job on its first real red:

```
tests/unit/scripts/test_mutation_gate.py::TestGateVerdictStaleness::test_a_fresh_report_does_not_block_on_staleness
```

## Why it failed, and why "flaky" was wrong

The test wrote a report **sixty seconds old** and asserted the gate would not call it stale.

The gate does not measure age. `gate_verdict` asks whether the report predates the **last scheduled
run**, and `_mutation_gate.py:42` sets `NIGHTLY_HOUR = 3`. So between **03:00:00 and 03:01:00** a
sixty-second-old file is from before 03:00 — yesterday's business — and the gate blocks. Correctly.

The nightly runs at 03:00.

Reproduced before touching anything, by pinning the clock and running the shipped code:

| Clock | Report age | `blocked` | Old assertion |
|---|---|---|---|
| 03:00:30 | 60 s | `True` | **FAIL** |
| 10:00:00 | 60 s | `False` | pass |

Deterministic, not flaky. It fails inside a sixty-second window, and that window is the one the
suite runs in. It had read as intermittent for four nights.

## What it cost

A red baseline voids every verdict in the session. **145 mutants judged, all meaningless** —
including the five `TECH-056 FR-1` mutants, which returned `UNMEASURED [scope-already-red]` because
they live in the same file. `mutation.py --gate` has been BLOCKED on those five ever since, and they
were never findings about the code.

## The fix

The production code is right. The test was wrong, and its wrongness was *reading an input it did
not control*.

| # | Change |
|---|---|
| 1 | `TestGateVerdictStaleness` pins `now` via `_at()`, which patches the **module's own `time` name** — not the global `time` module, so nothing else in the process sees a frozen clock |
| 2 | `_report` takes an absolute `written_at` instead of `age_seconds`. "Fresh" is a position against the schedule, not a duration |
| 3 | Two new tests hold the boundary the old one straddled: at 03:00:30 a report written at 03:00:20 is current, and one written at 02:59:30 is stale |
| 4 | The class docstring carries the whole story, so the next reader does not re-derive it |

The two sibling tests using `age_hours=47`/`49` were left alone: any age of 24 hours or more is
always before the last expected run, whatever the clock says, so they cannot flake. Checked, not
assumed.

## Probes — and a gap they closed

`FR-11` says the system *"SHALL treat a missing or stale report as blocking"*. The corpus had **no
mutant for it**: staleness was tested and never re-measured. Both directions are now pinned under
`TECH-049 FR-11`.

| Neutralised | Objections | Named by |
|---|---|---|
| `if mtime < expected:` → `if False:` (a stale report reads as current) | 50 | `test_a_report_older_than_the_last_run_blocks` · `test_during_the_run_minute_a_report_from_before_it_still_blocks` |
| `if mtime < expected:` → `if True:` (every report reads as stale) | 60 | `test_a_fresh_report_does_not_block_on_staleness` · `test_during_the_run_minute_tonights_report_is_current` |

Each direction is named by one old test and one new one, which is the point: the old pair could not
tell the two apart at 03:00:30.

## Results

| Check | Result |
|---|---|
| full suite | **8,392 passed, 11 skipped** in 85 s |
| `quality.py cb` | 14 passed, 1 skipped |
| `quality.py doc` | 13/13 |

`mypy` reports 6 pre-existing `no-untyped-def` errors in this test file. Confirmed identical at
`HEAD` before the change; test files are outside the gate's mypy scope. Not introduced here, and
not fixed here.

## Not fixed here, and named

- **The five `TECH-056` findings stay BLOCKED.** They clear when a green baseline re-measures them.
  An agent dispositioning its own run's findings is the exact defect `TECH-056` was written to stop.
- **The 4 STALE / 18 UNHASHED anchors** in the 2026-08-26 session are untouched.
