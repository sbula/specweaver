# Walkthrough: `TECH-056` — a scoped run withdrew findings it never looked at

- **Ticket**: none, by the `TECH-049 FR-11` precedent. The record is this file, the test
  docstrings, and five mutants in the nightly corpus
- **Kind**: bugfix · **DAL-C** · 2026-08-27 · **CB-3 of 7**

## The failure

`fold_session` closed any open finding absent from the run's `declared` set, as `withdrawn` —
*somebody deleted this mutant*. That is right for the nightly, which sweeps the whole corpus.

It is wrong for `mutation.py --corpus <one file>`, which declares one campaign's mutants. Every
finding on every other campaign is then absent for the trivial reason that nobody asked about it.

Reproduced against the shipped function, three inputs, no filesystem:

```
one open finding + one run of an unrelated campaign
  -> {'at': 1000.0, 'state': 'closed', 'reason': 'withdrawn'}
```

**This is the defect `declared` was added to prevent, arriving through the door it left open.** Its
own docstring says so: *"without it a mutant that never ran cannot be told from one somebody
deleted, and those close for opposite reasons — the second is how a ledger could be cleared by
removing campaigns and read as a year of diligent fixing."* The guard held against deletion and
not against narrowing.

## What it cost

Nothing, by luck. The ledger held no open findings the week it was found — the 2026-08-27 nightly
had closed the last five legitimately, against a green baseline. Two scoped runs during CB-1 folded
into the real ledger and took nothing with them.

That is luck, not design. It is also why this boundary sends its own scoped runs to a private
`--out`.

## The fix

`fold_session` and `record_run` take `full_sweep`. Absence means *deleted* only when the run looked
everywhere; otherwise the entry is left exactly as found.

| Case | Before | Now |
|---|---|---|
| full sweep, not declared | `withdrawn` | `withdrawn` |
| scoped, not declared | `withdrawn` | **untouched** |
| declared, judged `PROTECTED` | `fixed` | `fixed` |
| declared, no verdict | `unreachable` | `unreachable` |

**Untouched, not merely unclosed.** `last_seen` and `occurrences` do not move either — an entry
that recorded a sighting on a night nothing examined it would inflate the recurrence count, and
that count is the only pressure on a `will-fix` nobody gets to. A test asserts the entry is equal
to what it was.

**`full_sweep` defaults to `False` `[agreed 2026-08-27]`**, because the two mistakes are not
symmetrical. A caller that forgets it under-closes, and an unclosable finding is visible every
morning. The other default over-closes, and a finding that vanished is visible nowhere.

## The wiring, and why it needed its own test

`full_sweep = bool(args.corpus_dir) and not args.corpus`.

A bare `--corpus-dir` is the operator saying *I swept this tree* — it is what the systemd unit
passes. Naming individual corpora is not, and the two mixed is a narrowed sweep that states the
completeness of neither.

A `--corpus-dir` pointed somewhere empty cannot exploit this: it discovers no corpora, so there are
no campaigns, and `main` folds nothing into the ledger at all.

`fold_session` cannot work any of this out. From inside, a scoped run's `declared` set is
**identical** to a whole-corpus run whose campaigns were deleted. So the unit tests prove the rule
and not the wiring — if `main` never passed the flag, every scoped run would go on withdrawing and
every unit test would still pass. `TestMainDeclaresTheRunsReach` drives the argument parsing and
the real `record_run` call, with only the worktree and the judging stubbed.

## Probes

| Neutralised | Objections |
|---|---|
| every run may withdraw (`if False`) | 3 |
| no run may withdraw (drop `full_sweep` from the guard) | 10 |
| the unsafe default (`= True`) | **1** |
| a scoped run claims the whole tree (`full_sweep = True`) | 2 |
| the nightly stops claiming its sweep (`full_sweep = False`) | **1** |

All five are in `TECH-056`'s `FR-1` campaign, anchored on `fold_session` and `main` and pinned
through `--refresh`. A withdrawal closes a finding with **no human disposition**, which is `FR-1`
defeated from a direction the original ticket did not consider.

The default and the nightly-sweep mutants have one protector each. Recorded rather than padded:
each is a single boolean with one observable consequence, and a second test would assert the same
thing twice.

## Two corpus repairs this turned up

- **`a-red-baseline-reads-as-green` was still in `TECH-056`** after CB-1 moved that claim to
  `TECH-049 FR-3a`. Its anchor no longer existed, so it returned `UNMEASURED [symbol-drifted]`.
  Deleted here: two campaigns asserting one claim is the second copy `PRINCIPLES.md` §5 forbids,
  and this was CB-1's loose end.
- **`full_sweep: bool = False,` is the signature of two functions.** The corpus runner refused the
  ambiguous anchor rather than guessing which one it changed — `anchor appears 2 times … make it
  unique`. Re-anchored on the two-line form that names `fold_session`'s `now:` above it.

Four older `FR-1` anchors drifted when CB-1 and CB-3 edited `gate_verdict` and `fold_session`, and
were re-pinned **after** the run re-verified them.

## Results

| Check | Result |
|---|---|
| full suite | **9,009 passed, 11 skipped** in 91s (was 9,001) |
| `quality.py cb` | 14 passed, 1 skipped, 0 failed |
| `quality.py doc` | 14 passed, 0 failed |
| `tests.py cb TECH-056 --kind bugfix` | unit + integration, ok |
| `TECH-056` corpus | 9 judged, **9 protected**, 0 unprotected, 0 unmeasured, 0 stale |

## Not fixed here, and named

- **Nineteen `fold_session` call sites in `test_mutation_ledger.py` now say `full_sweep=True`.**
  That is a claim, not boilerplate: every test in that file asks what a session concludes from a
  finding *not appearing*, and only a whole-corpus run can conclude anything from that. The file's
  own module docstring says so, beside the two rules it already carried.
- **One finding is open in the committed ledger, and an agent must not close it.** My scoped runs
  passed `--out` to a scratch path but left `--ledger` at its default, so they folded into the real
  ledger. Under the old rule that would have withdrawn all 29 findings; under the new one it
  withdrew none, which is the fix demonstrating itself on live data. What it did leave is
  `TECH-056 FR-1 a-red-baseline-reads-as-green` reopened as `UNMEASURED [symbol-drifted]` — the run
  that saw it was the one before I deleted the mutant from the corpus. It is genuinely gone, so the
  next `--corpus-dir` nightly closes it as `withdrawn` on its own. **Dispositioning it here is the
  precise act `TECH-056` exists to forbid**: an agent clearing a finding its own run produced.
  `--ledger` belongs in the scratch flags beside `--out` for a by-hand run; it was not, and this is
  the record of that.

- **The record still does not say which kind of run wrote it.** `full_sweep` is computed in `main`
  and passed straight to `record_run`; it is not in `session`. **CB-4** puts the run's scope in the
  record, which is what lets the *gate* refuse a scoped record rather than only the ledger.
