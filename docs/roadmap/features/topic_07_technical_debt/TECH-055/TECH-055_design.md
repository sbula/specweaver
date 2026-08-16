# Design: The Suite Edits the Standard It Is Measured Against

- **Feature ID**: TECH-055
- **Epic**: Topic 07 (Technical Debt)
- **Status**: APPROVED (2026-08-16)
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-055/TECH-055_design.md
- **Origin**: 2026-08-16, found at `TECH-054` CB-2 — an unexplained modification in `git status`
  after a full suite run. `TECH-054` recorded it and did not fix it; this ticket owns the repair.

> **Proportionality.** One autouse fixture and a one-argument fix to the test that caused it. The
> guard is the deliverable, not the single instance it catches.

## Problem Statement

`tests/integration/scripts/test_mutation_seam.py:234` called

```python
mutation.main(["--corpus", str(corpus_file), "--out", str(out), "--no-baseline"])
```

with no `--ledger`, so `mutation.py` fell back to its default and `_gate.record_run` appended to the
**real** `scripts/baselines/mutation_findings.json` on every suite run. The result was a phantom
finding — `D-SENS-09 FR-97 orphans-empty`, for a mutant that exists only inside a `tmp_path`
fixture — sitting in the file the morning `mutation.py --gate` reads and asks somebody to have read.

**The instance is small; the class is not.** `scripts/baselines/` holds sixteen version-controlled
files, one per gate: the uncited-FR count, the clone count, the delivered-claims ratchet, the
proof-tier ratchet. They are the standard the repo is measured against, and **nothing compares a
baseline to what it used to be.** A test that rewrites one relaxes a gate permanently, inside a diff
that reads as ordinary test work. This one happened to make a gate stricter rather than looser,
which is luck, not a mitigation.

It was found by noticing a stray `M` in `git status`. That is not a detection mechanism, and the
next occurrence would land in a commit nobody looked at that closely.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | No test may leave a gate baseline rewritten | Any test in any tier | writes, adds or deletes a file under `scripts/baselines/` | that test fails, naming every affected file and what happened to it |

**One requirement.** The `--ledger` fix is not a second one — it is the first thing FR-1 catches,
and a requirement that says "and also fix this one call site" is a task list wearing a ledger row.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Cheap enough to run before and after **every** test | The directory hashes in ~0.12 ms (measured, 100 KB over 16 files), so two snapshots per test cost ~2 s across 7356 tests, spread over the xdist workers. A guard that costs a minute gets an opt-out flag, and then it guards nothing |
| NFR-2 | The guard must not itself write to the directory | It fails the offending test rather than restoring the file. Silently rewriting version-controlled content is the exact act it exists to catch. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-3 | One failure per offence, no cascade | The next test's "before" is the polluted state, so only the writer fails. Otherwise the first offender buries itself in a hundred downstream failures **[proof: meta — rule about tests, docs or the diff]** |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | An autouse fixture in the root `tests/conftest.py`, not a gate script | It has to catch the write *while the writer is on the stack*; a post-hoc `git status` check in `quality.py` would name the suite, not the test. Same argument the colour block at the top of that file already makes: **it protects tests nobody has written yet** | No |
| AD-2 | Logic in `tests/baseline_snapshot.py`, not inline in the fixture | A fixture cannot be unit-tested; a function can. This is what keeps FR-1 provable rather than merely present | No |
| AD-3 | Content hash **and** `mtime_ns`, not either alone | Reversed during the boundary, on evidence. Content alone answers *did a gate's standard move* — the damage — and misses *did a test write here* — the act. `record_run` rewrites the ledger byte-identically when it has nothing to report, so a second writer stayed invisible to the content-only draft and would have spoken only on the day a finding existed, which is the one day the contents matter. `mtime_ns` changes on write and not on read, so it flags the act without flagging inspection | No |
| AD-4 | Fail, do not restore | See NFR-2. Restoring would also silently discard a concurrent legitimate edit — `_corpus.py --refresh` in another terminal — which is worse than a failed test | No |

## Sub-Feature Breakdown

**Single feature — no decomposition.** One fixture, one helper, one changed argument.

## Execution Order

One commit boundary: the helper and its unit tests, the fixture, the seam-test fix, in that order —
the guard must be armed **before** the fix, or nothing proves it fires.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | Single feature | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: DELIVERED 2026-08-16. Full suite green at 7374 passed / 11 skipped, with
`scripts/baselines/` untouched afterwards.

The guard was armed before the fix and caught the known defect on its first run — an ERROR in
`test_no_sandbox_path_survives_into_the_written_report`'s teardown, naming
`mutation_findings.json: changed`.

**There was a second writer, and the first draft of this guard could not see it.**
`tests/e2e/scripts/test_mutation_nightly.py` runs the *entire* real corpus through `mutation.py`
with no `--ledger`, so every suite run folded its report into the real ledger. Most runs write
byte-identical content, so a content-only comparison stayed silent — and would have spoken only on
the day a blocking finding existed, overwriting the recurrence counts the morning gate depends on at
exactly the moment they mattered. It was found by reading the callers, not by the guard, which is
the failure this ticket exists to end.

`snapshot` now records `<sha256>@<mtime_ns>`. Re-running that e2e with its `--ledger` removed fails
in teardown, so the strengthening is proven and not merely argued. Both call sites now pass a
`tmp_path` ledger, and with the fixture live no other test in any tier writes to the directory.

**Resolved 2026-08-16, after measuring.** `test_mutation_nightly.py` ran the **entire** real corpus
inside the suite: **117.3s of a 178s run**, the critical path of every full sweep, growing with every
campaign anybody wrote. It now points `--corpus-dir` at one feature directory — **4.3s**, and flat
from here — while the real nightly still walks the whole tree, which is what the timer's `ExecStart`
says and what `test_mutation_timer_units.py` asserts.

Narrowing the directory would have cost the only coverage `discover_corpora` had, so that moved to
its own test: a filesystem walk over the real tree in 0.01s, asserting **every** corpus is found
against the `<ID>/<ID>_mutants.json` naming contract. The old assertion only checked that `TECH-049`
appeared among the results, so a corpus that went missing failed nothing.

Parallelising the session was considered and rejected for now: it would speed up an unattended 03:00
job with a whole night of slack, while the cost that was actually being paid sat in every commit
boundary. Revisit when the nightly's own wall clock is the complaint.

