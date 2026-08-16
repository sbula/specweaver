# Design: 24 Tests Look Like Coverage and Never Run

- **Feature ID**: TECH-051
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: 2026-08-16, `INT-US-16` CB-1. Checking whether the runner's telemetry flush was
  already covered at unit tier before writing a duplicate test.

## Problem Statement

`tests/unit/core/flow/engine/test_runner_telemetry.py` contains six tests for the pipeline runner's
telemetry flush — including `test_flush_called_on_failed_run`, which is the only thing in the repo
that ever claimed to prove a failed run still records what it spent. **The file collects zero
tests.** Its class is named `QARunnerTelemetryFlush`, and pytest collects `Test*` only.

Measured across the whole suite the same day:

| | |
|---|---|
| test files on disk | 568 |
| excluded only by the `live` marker — legitimate | 13 |
| **uncollectable at all** | **12** |
| ├ a class holding `test_*` methods, not named `Test*` — **silent holes** | **3** |
| └ files defining nothing at all — dead stubs | 9 |

```
10  tests/integration/assurance/validation/test_kind_presets.py
 8  tests/unit/core/flow/engine/test_runner_events.py
 6  tests/unit/core/flow/engine/test_runner_telemetry.py
24  tests that exist, look like coverage, and have never run
```

The 9 stubs are the whole `tests/unit/sandbox/protocol/` package — empty files, at least honestly
empty. **The 3 silent holes are the dangerous kind**: they read as coverage in a directory listing,
in review, and to anyone deciding not to write a test because one appears to exist. That last is not
hypothetical — it is exactly the decision `INT-US-16` was about to take.

**Reproduce it, do not trust a list.** The census is a measurement, not a fact to copy:

```bash
.venv/bin/python -m pytest --collect-only -q -p no:tach \
  --override-ini="addopts=--import-mode=importlib" | grep '::' | cut -d: -f1 | sort -u
```

Compare that against `find tests -name 'test_*.py'`. The `--override-ini` is load-bearing: the
repo's `addopts` carries `-v`, which turns `--collect-only -q` into a tree rather than node ids —
a first attempt at this census parsed the tree and reported all 568 files as empty.

## Goal

No test file can exist in this repo and contribute nothing without a gate saying so. The 24 hidden
tests either run, or are deleted for a stated reason.

## Relationship

- **`R6`** (`scripts/_test_class_naming.py`) already requires a test class to name the symbol under
  test, and would have flagged `QARunnerTelemetryFlush` on its name — but it has no opinion on
  whether the class is **collected**, which is the property that actually matters here. Same blind
  spot as the one `TECH-050` closed when `R6` could not see `tests/` helper modules.
- **`_silent_skips.py`** catches a test that skips itself. This is the tier below: a test that is
  never asked to run at all.
- **`check_proof_tier.py`** sweeps delivered contracts for proof that does not exist. A cited proof
  file that collects nothing would satisfy it today.

## Candidate Approaches (not yet designed)

1. **A `quality.py doc` (or `cb`) check that every `test_*.py` contributes at least one node id.**
   Cheapest, and it catches all three causes at once — bad class name, empty file, and any future
   variant. Cost: it needs a collection pass, which is seconds, not free.
2. **Extend `R6` to reject a `test_*` method inside a non-`Test*` class.** Narrower and static — no
   collection pass — but it misses empty files and anything else that stops collection.
3. **Both**: R6 for the fast diff-scoped signal, the collection census as the ratcheted backstop.

Separately, and independent of which is chosen: decide per file whether the 24 hidden tests are
**fixed** (rename the class, then face whatever they were never asserting) or **deleted**. Assume
neither — a test that has never run has never been true, and renaming three classes may turn 24
green ticks into 24 failures. That is the point of the ticket, not a risk to it.

## Non-Goals (proposed, pending design)

- The 9 empty `sandbox/protocol` stubs. Deleting them is trivial and probably right, but *why* a
  whole test package is empty is a question about `protocol`, not about collection.
- Anything about the `live` marker. Those 13 files are excluded on purpose and correctly.
- Coverage percentage as a metric. The claim here is binary — collected or not.

## Next Step

Run `specweaver-design TECH-051`. The design must decide between the three approaches and, before
that, **re-run the census** — the numbers above are from 2026-08-16 and the whole lesson of this
ticket is that a stale list of tests reads exactly like a fresh one.
