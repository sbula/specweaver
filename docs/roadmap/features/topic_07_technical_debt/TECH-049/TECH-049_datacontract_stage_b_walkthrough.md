# Walkthrough — data contract, Stage B

**Killers carry `in_scope` and the reason they objected.**

## What changed and why

A killer was a bare node id. That cannot distinguish a mutant killed by the guard we planted from
one killed by an unrelated fixture error or a broken import — both read as a kill, and the campaign
then certifies a requirement nothing protects. `reprcrash.message` was present on every failed
record and discarded.

| File | Change |
|---|---|
| `scripts/_mutate.py` | `_crash_message()`, `killer_records()`; `run_pytest` returns records; `run_one` carries them |
| `scripts/_mutation_verdict.py` | `scope_killers()` — marks each killer with whether the campaign named its file |
| `scripts/mutation.py` | `MutantRun.killer_records`; the judging site scopes them, and emits `explanation` |

Killers are **marked, never filtered**: a bystander that objected is evidence about the scope, and
dropping it leaves a reader unable to see why the verdict went the way it did.

## Test results

| Tier | Result |
|---|---|
| unit | 7022 passed, 11 skipped |
| integration | 764 passed, 15 deselected |
| e2e | 242 passed |
| **full suite** | **8028 passed, 11 skipped** |

Quality: commit gate 14 passed / 1 skipped / 0 failed. Doc gate 12/12. `tach` clean. Comment
provenance clean.

## HITL gates

**Phase 1+2 combined gate — presented, answered.** Two architecture findings and a four-story test
gap. The user answered *"do all 4, especially 4"*. All four implemented.

**Phase 7.5 — pending.** Red/Blue review of the diff.

## What the gate caught that the work had missed

The composition-and-agreement check (§2.5c) found the real defect. `run_pytest`'s return grew from
two values to four, then to five, **and every unit test passed both times** while a real session
died on the unpack — four separate monkeypatch doubles had not grown with it. A mock proving the
mock, twice in one afternoon.

Fixed in both directions:

- **A test** that calls the real `run_pytest` against a real pytest run and asserts the arity, the
  order and the types. Removing one returned value now fails three tests; before, it failed none.
- **The cause.** The four scattered lambdas are one shared `fake_run_pytest` helper, so the shape
  cannot drift per test. Consolidating them surfaced two doubles still returning a 2-tuple —
  stale since that morning, passing only because `confirm_kill` was patched alongside them.

## Architecture findings, carried forward

Neither is introduced by this stage; both are recorded rather than silently skipped.

| # | Finding | Disposition |
|---|---|---|
| A-1 | `_mutate.py:197` names its raw outcome `verdict`, which now means something else in the vocabulary | Rename to `outcome` in Stage F, with the rest of the vocabulary rename |
| A-2 | `_mutate_campaign.py` still documents and emits `KILLED`/`SURVIVED` — a sibling tool on the retired vocabulary | Stage F |
