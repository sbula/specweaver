# Walkthrough: `TECH-049` — the store keeps a failure until it is fixed

- **Ticket**: none, by the `FR-11` precedent in this directory. The record is this file, the test
  docstrings, and six mutants in the nightly corpus
- **Kind**: bugfix · **DAL-C** · 2026-08-27 · **CB-6 of 7**

## The rule

CB-5 gave every run its own record and nothing pruned them. The obvious rule is age, and age is
wrong.

**Retention is tied to state** `[agreed 2026-08-27]`: a record is deleted only when a later
`PASSED` record of covering scope supersedes it. A record of a failure is kept until the failure is
fixed and a clean run that actually looked at it proves so, however long that takes.

Age says nothing about whether anybody acted on what a record found. A fourteen-day sweep deletes
the evidence of a fault nobody has looked at yet — which is precisely the evidence worth keeping —
and `.tmp/` is gitignored, so no diff and no gate would ever show what went missing.

| | Superseded? |
|---|---|
| `FAILED`, then a later `PASSED` full sweep | yes |
| `FAILED` full, then a later `PASSED` **scoped** run | **no** |
| `NOT_RUN`, then any later `PASSED` | **no** — an error is kept exactly as a failure |
| `PASSED`, then a later `PASSED` of covering scope | yes |
| anything, then a later **`FAILED`** | no — a newer red run is more evidence, not less |
| the newest record | never — nothing is later than the latest |

A scope that cannot say what it covered covers nothing. Reading silence as *everything* is the
mistake the gate refuses one level up, and it is worse here: there it blocks a morning, here it
deletes evidence.

## No cap, and a warning instead

An unfixed repo grows the store for ever. That is the honest consequence and it is accepted: a cap
deletes the record of an unfixed fault, which is the one thing this rule exists to prevent.

So the run warns past **20** unsuperseded records `[agreed 2026-08-27]` and deletes none of them.
`overgrown` returns prose and has no path that names a file — there is a test asserting exactly
that, because the temptation to add "…and remove the oldest" is the whole risk.

The count is of what is **left after** superseding, not what is on disk: a healthy store passes
twenty records the moment somebody runs the corpus twenty-one times, which is a Tuesday.

`.tmp/` is invisible to every gate in this repo — the handover reached 23 MB there before anyone
noticed — so the warning is printed by the run **and** by `--gate`.

## The sweep runs at the start of a session

Not the end. A run that crashes never reaches its own end, and a crashing run is exactly what keeps
producing the records worth sweeping, so pruning on the way out stops happening precisely when it is
needed. There is a test that kills the session mid-judging and asserts the store was swept anyway.

## Probes

| Neutralised | Objections |
|---|---|
| a narrow pass supersedes a wide failure | 4 |
| any later record supersedes, not only a pass | 3 |
| the backlog warning never fires | 2 |
| pruning deletes a failure | **1** (was **SILENT**) |
| the sweep never runs | 2 |

**One mutant was SILENT and found a hole in my own tests.** Deleting *everything but the newest
record* passed every `sweep` test I had written: one had a single record, the other had two where
the older was genuinely superseded. Neither could tell the two behaviours apart.
`test_a_wide_failure_survives_a_later_narrow_pass_on_disk` is the case that does — an older record
that must stay, with a newer one sitting after it.

**And one mutant read UNPROTECTED for the reason `STATE.md` warns about.** `the-sweep-never-runs`
was filed under `FR-11`, whose declared scope is the gate's tests; the test that kills it lives in
the ledger seam, which `FR-9` owns. Unprotected *by construction*, and it reads exactly like a real
coverage gap. Moved to `FR-9`, protected.

## `mutation.py` hit its ceiling, and the flagged extraction happened

CB-5 recorded that the next addition to `mutation.py` needed a real extraction and named the seam.
It did.

`_cli_commands.py` now holds `--confirm`, `--gate`, `--install-timer` and `--summary`. They share
nothing with the session runner except an argument parser: they read files, print prose and return
an exit code, while the runner builds worktrees and judges mutants. `mutation.py` went 600 → 554.

Then `main` failed the cognitive-complexity gate at 12, which is the same message from a different
check — deciding what to run and narrating it are different concerns. `announce_sweep` moved to the
CLI layer with them.

## Results

| Check | Result |
|---|---|
| full suite | **9,058 passed, 11 skipped** in 91s (was 9,033) |
| `quality.py cb` | 14 passed, 1 skipped, 0 failed |
| `quality.py doc` | 14 passed, 0 failed |
| `TECH-049` corpus | 25 judged, **25 protected**, 0 unprotected, 0 unmeasured, **0 stale** |
| ledger | untouched — `--ledger .tmp/cb6_ledger.json` throughout |

## Not fixed here, and named

- **The store has no gate of its own.** Nothing fails a commit because the backlog grew; the
  warning is printed by the run and by `--gate` and read by whoever is looking. That is deliberate
  — `NFR-6` forbids the session gate from being a `quality.py` check, and a backlog warning is the
  same class of standing decision.
- **`.tmp/mutation_session.json` and the rest of `.tmp/` are still orphaned.** The new rule governs
  the store only. **CB-7** sweeps what is left, once, by hand and with the list in front of you.
