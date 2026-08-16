# Implementation Plan: The Suite Edits the Standard It Is Measured Against

- **Feature ID**: TECH-055
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-055/TECH-055_design.md
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-055/TECH-055_implementation_plan.md
- **Status**: APPROVED (2026-08-16)

**FRs owned: FR-1.** One commit boundary.

## CB-1 — arm the guard, then fix what it catches

Order matters and is the point: `tests/baseline_snapshot.py` and its unit tests, then the autouse
fixture in `tests/conftest.py`, and only then the `--ledger` argument in
`test_mutation_seam.py:234`. Fixing the call site first would have left nothing to prove the guard
fires, which is the failure mode this whole ticket is about.

It did fire. With the fixture live and the call site still broken, the offending test ERRORed in
teardown with `mutation_findings.json: changed`.

**Then a second writer turned up that the guard could not see**, and it changed the design.
`tests/e2e/scripts/test_mutation_nightly.py` runs the *entire* real corpus through `mutation.py`
with no `--ledger`. Most runs fold an empty finding set and rewrite the ledger **byte-identically**,
so the content-only first draft stayed silent; it would have spoken only on the day a blocking
finding existed, which is the day the recurrence counts it would overwrite actually matter. Found by
reading the callers — the very method this ticket exists to replace.

`snapshot` now records `<sha256>@<mtime_ns>`, and `rewrites` distinguishes *changed* from *rewritten
with identical content*: the first says a gate's standard moved, the second says a latent writer is
present and will move it as soon as it has something to say. Verified by removing that e2e's
`--ledger` again and watching it ERROR in teardown.

## Proof, per tier

| Tier | What it proves | Where |
|---|---|---|
| unit | the comparison: changed / rewritten-with-identical-bytes / added / deleted / nested / non-UTF-8 / missing directory / cost | `tests/unit/test_baseline_write_guard.py` (13) |
| integration | the comparison is **reached** — `autouse` is set, the fixture watches the real directory, and its body fails a test when handed a rewrite | `tests/integration/test_baseline_guard_wiring.py` (5) |
| e2e | — | none; see below |

**The integration tier is the load-bearing one**, not padding. Delete the fixture from
`tests/conftest.py` and all thirteen unit tests still pass while every test in the repo regains the
ability to rewrite a gate ratchet. That is the same shape as the defect being repaired: logic that
was right and unreached. The wiring test drives the **real** fixture function out of
`tests/conftest.py` — not a copy — with `snapshot` monkeypatched to hand it a before and an after.

**No e2e, and the reason is not "it was awkward."** A genuine end-to-end would run a child pytest
that really rewrites a baseline, which needs `BASELINES` redirectable from the environment — and an
environment variable that moves a guard's target is an off-switch for that guard. A test that can
only be written by weakening the thing it tests is the wrong test. The evidence it would have
supplied is supplied instead by the mutation campaign, which runs the real suite in a sandboxed
worktree with the fixture genuinely broken.

## Done when every mutant is killed

`TECH-055_mutants.json`:

| Mutant | Result |
|---|---|
| the guard is not `autouse` | KILLED ×1 |
| the guard detects and never fails | KILLED ×2 |
| a changed file is not reported | KILLED ×4 |
| a deleted baseline is not reported | KILLED ×3 |
| a missing directory is silently empty | KILLED ×1 |
| the snapshot forgets **when** a file was written | KILLED ×1 |
| the snapshot forgets **what** a file contains | KILLED ×1 |

**Mutating a suite-wide autouse fixture is self-referential, and the first attempt read as BROKEN.**
Inverting `!=` to `==` in `rewrites` makes the guard report every *unchanged* baseline, so it errors
sixteen tests in teardown — and `is_broken()` cannot tell that from a collection failure, so the
runner correctly refuses to call it a survival and the campaign proves nothing. The mutant was
rewritten to fail **closed** (miss a real change) rather than **open** (invent changes). Recorded in
`docs/dev_guides/writing_mutation_campaigns.md`, because nothing about it is specific to this
ticket.

Four mutants are killed by exactly one test each — including `the-guard-is-not-autouse`, which by
construction *only* the wiring test can see. Recorded rather than padded.

The last two are the mtime/content split, and they are worth reading together: forgetting *when*
makes a latent writer invisible, forgetting *what* keeps every write visible but reports the
harmless version of it. Neither half is redundant, which is why both are pinned.

## Out of scope

- **A `quality.py` check that greps `git status` after a suite run.** It would name the suite, not
  the test, and the whole value here is catching the write while its author is on the stack.
- **The other fifteen baseline files' semantics.** This guards them all identically, by content and
  write time;
  what any individual ratchet *means* stays with its own gate.
- **`mutation.py`'s default ledger path.** Defaulting to the real ledger is correct for the nightly
  run; the defect was a caller that did not override it.
