# Walkthrough: `TECH-049` — one path meant the last writer won

- **Ticket**: none, by the `FR-11` precedent in this directory. The record is this file, the test
  docstrings, and four mutants in the nightly corpus
- **Kind**: bugfix · **DAL-C** · 2026-08-27 · **CB-5 of 7**

## The failure

`--out` was one file at one fixed path. The nightly wrote it at 03:04, a by-hand run wrote it at
05:13, and the nightly's 187-mutant result was **gone** — not stale, not refused, absent, with no
copy anywhere.

CB-4 taught the gate to refuse what it found there. That is the safe half and it does not bring the
nightly's answer back.

## The store

Every run writes `.tmp/sessions/<started_at>_<scope>.json`. The gate picks **the newest record that
answers for the corpus**, not the newest record.

```
$ ls .tmp/cb5_sessions/
2026-08-27T09-13-55.848421-00-00_full.json
```

Newest-that-covers is the whole point. A scoped run five minutes ago says nothing about the
campaigns it skipped, however recent it is — and under one path it did not merely out-rank the
nightly, it destroyed it.

| Store holds | Gate answers from |
|---|---|
| two full sweeps | the newer one |
| a full sweep and a newer scoped run | **the full sweep** |
| only scoped runs | nothing — blocks |
| nothing, or no directory | nothing — blocks |
| a full sweep and a half-written newer file | **the full sweep** |

That last row is deliberate. A run killed mid-write leaves a corrupt file; a selection that raised
would make every good record unreachable because of the newest byte.

## The filename carries two facts and neither is decoration

**Microseconds.** `started_at` is used whole. Truncating to seconds looks tidier and lets a nightly
and a by-hand run that started in the same second collide — the exact loss the store exists to
prevent, reintroduced by rounding.

**Sanitisation.** An ISO timestamp carries `:` and `+`; a corpus name is untrusted enough that
`../` reaching the filesystem would let a scope name a path outside the store. The label drops
dots too, because `.` has to survive in the timestamp for microseconds and `..` must not survive
anywhere.

`record_name` takes **the whole document**, not its parts. This module owns the record's shape, and
a caller assembling a name from `started_at` and `scope` would be a second place that has to know
those key names — the drift `SESSION_BLOCK` exists to stop, one level down.

## The systemd unit needed no change

`ExecStart` passes no `--out`, so it inherits the new default. Checked rather than assumed.

## Two things this caught in my own work

**The one-name-one-place guard from CB-2 fired on me.** I wrote `document["session"]["started_at"]`
in `mutation.py` — a literal spelling of the block name outside the module that owns it. The
agreement test failed on the next run, named both files, and I used `_report.SESSION_BLOCK`.

**A delivered assertion was stricter than its own requirement.** `test_the_timers_command_line_runs_the_real_corpus`
asserted `"/tmp/" not in` the record. `NFR-3` says no **sandbox** path may survive, and a sandbox
is `/tmp/sw-`. The broader claim held only while no mutant's captured output happened to mention
another `/tmp` path — and one now does: pytest rewrites
`assert latest_covering_record(store) is None` into a message containing that test's own
`tmp_path`, which is neither a sandbox path nor anything the sanitiser should touch.

Narrowed to `/tmp/sw-`, which is what `NFR-3` says. **This is a weaker assertion than what shipped
and it is recorded here rather than made quietly** — the test now asserts the requirement instead
of a proxy that happened to be stricter.

It failed only under `-n auto` and passed alone, because the leak came from another test's temp
directory. That is trap 2's shape from a new direction.

## Probes

| Neutralised | Objections |
|---|---|
| the newest record wins regardless of scope | 3 |
| the oldest covering record is chosen | **1** |
| the timestamp loses its microseconds | **1** |
| a scope reaches the filesystem raw | **1** |

Two under `FR-11` (selection), two under `FR-9` (the record). All pinned through `--refresh`.

## `FR-9` corrected, second clause

The row said *one `.tmp/mutation_session.json`*. It now says one record per run into a store
`[agreed 2026-08-27]`. Both of its corrections are noted beside it: the block's name in CB-1, the
path in CB-5.

## Results

| Check | Result |
|---|---|
| full suite | **9,033 passed, 11 skipped** in 90s (was 9,023) |
| `quality.py cb` | 14 passed, 1 skipped, 0 failed |
| `quality.py doc` | 14 passed, 0 failed |
| `TECH-049` corpus | 20 judged, **20 protected**, 0 unprotected, 0 unmeasured, **0 stale** |
| ledger | untouched — `--ledger .tmp/cb5_ledger.json` throughout |

## Not fixed here, and named

- **`mutation.py` sat at 605 lines and is now 600**, which is the ceiling exactly. Two comments
  restating rationale that `_run_reach.py` already carries were cut, and `record_name` taking the
  document removed the last line. **The next addition to this file needs a real extraction** — the
  `_cmd_*` handlers are the seam, as `_mutation_timer.py` was before them.
- **`.tmp/mutation_session.json` and its `.md` are now orphaned**, along with the rest of `.tmp`.
  **CB-7** sweeps them; nothing reads them as of this boundary.
- **Nothing prunes the store yet.** Every run adds a file for ever. **CB-6** is the retention rule
  — a record is deleted only when a later `PASSED` record of covering scope supersedes it, with a
  warning past 20 unsuperseded.
