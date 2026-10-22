# Why the rules exist

The incidents behind the rules in `SKILL.md`. Each rule stays in the skill; this file keeps the story.

## Contents
- Prerequisites green in code (1.0d)
- Integration is implicit
- A cross-feature test is written when its interface is defined
- The matrix never asks whether the unit is used alone

## Prerequisites green in code (1.0d)

Document state lies: INT-US-21's three prerequisites were all marked `✅` and all three were
materially broken (handlers never registered; a field documented as hook-populated with zero
writes in `src/`; a required enum that cannot be YAML-serialized). This checks the evidence,
not the checkbox.

## Integration is implicit

A seam FR proven by a unit test with the other side mocked proves the mock, not the contract.
`TECH-041` is one instance: `C-VAL-03` is `✅` and its DAL override is proven link by link, never as
a chain.

A missing spanning test under a finished (sub)story becomes a `TECH` ticket, the rule for every
other defect in closed code. Integration used to be the one carve-out, and the carve-out is what
grew a second registry: measured 2026-08-19, 31 of 36 open contract rows were tracking work that
another ticket already owned.

## A cross-feature test is written when its interface is defined

This is the whole point of writing it early: a test authored after the code is green on its first
run and asserts the present state rather than a contract. `strict=True` turns the eventual
unexpected pass into a failure, which is the signal that the marker is now stale and the test
stands on its own.

`check_xfail_blockers.py` fails any strict xfail whose named blocker has shipped, and any whose
reason names no blocker at all — an unnamed one can never be judged stale and becomes a permanent
exemption.

## The matrix never asks whether the unit is used alone

**THE MATRIX VARIES INPUTS. IT NEVER ASKS WHETHER THE UNIT IS USED ALONE.** Four defects on
2026-08-16 shared one shape, and every one of them had green tests in all four buckets throughout:

| | well covered | unreached |
|---|---|---|
| `TECH-054` | resume persistence — 14 tests, three tiers | how a run is *found* to resume |
| `TECH-055` | the baseline comparison — 11 unit tests | that the fixture is `autouse` at all |
| `TECH-056` | `gate_verdict` **and** `record_run`, separately | their composition — the gate could never block |
| `TECH-058` | both whole-suite runners | that the two agree — one had no `-n auto` |

So ask two more questions before you stop writing tests:

1. **Is this only ever used in sequence with something else?** Then a test of each end is not a
   test of the pair. `TECH-056`'s two functions each passed every assertion they had, while the
   composition they exist for could not work — because each unit test built the state it wanted
   instead of letting the other half build it.
2. **Does anything else in the repo do this same job?** Then assert that they **agree**. The
   asymmetry in `TECH-058` was plainly visible in both files and in neither test.

Neither question is answered by a bucket, because each half genuinely satisfies its own bucket.
Where the answer to either is yes, that test is **integration** even when both sides are pure —
the seam is the claim.
