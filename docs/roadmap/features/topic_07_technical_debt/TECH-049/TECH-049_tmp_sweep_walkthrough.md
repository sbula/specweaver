# Walkthrough: `TECH-049` — the scratch directory nothing had ever pruned

- **Ticket**: none, by the `FR-11` precedent in this directory. The record is this file
- **Kind**: chore · **DAL-C** · 2026-08-27 · **CB-7 of 7, last**

## What was there

**68 files, 892 KB, oldest 2026-08-14.** Nothing had ever pruned `.tmp/`, and nothing would have:
it is gitignored, so no diff, no gate and no review has ever seen its contents. That is the same
blind spot that let the handover reach 23 MB and 332,068 lines — 122 of them distinct — before
anybody noticed.

| Group | Files | What it was |
|---|---|---|
| `audit_*` | 7 | August 19 audit runs |
| `stage_a…e`, `rb*`, `json_check`, `dui01*` | 20 | August 20 red/blue and staging scratch |
| `t068*`, `t069*`, `reanchor*` | 6 | August 21–22 ticket scratch |
| `topics_superseded/` | 7 | see below |
| `mutation_session.json` / `.md` | 2 | the record CB-5 orphaned |
| `cb1…cb6*` | 24 | this session's own scratch |
| `measure_blob.py`, `test_output.log`, `s/bad_spec.md`, `session_brief_last.txt`, `dui01.log` | 5 | odds and ends, back to August 14 |

## The one group I would not delete on the agreement alone

`.tmp/topics_superseded/` is not scratch by its name. Seven files, ~110 KB, deliberately parked on
2026-08-25 — the **pre-conversion** topic registries, from before the seven-field rewrite.

`[agreed 2026-08-27]` covered "the stale scratch", and seven documents somebody chose to keep are
not obviously that. So they were checked rather than assumed:

```
topic_01_ui_glass: recoverable at 4db40a75
topic_02_sensors: recoverable at 4db40a75
topic_03_flow_engine: recoverable at 7d114725
topic_04_intelligence: recoverable at 7d114725
topic_05_validation: recoverable at d4e2814a
topic_06_sandbox: recoverable at 7d114725
topic_07_technical_debt: recoverable at a97c8e2d
```

Every one is **byte-identical** to a committed version, found by diffing each parked file against
every commit that touched its live counterpart. Git already holds them; the copies were a second
copy of a fact, which is what `PRINCIPLES.md` §5 is about.

## What is left

```
.tmp/HANDOVER.md
```

One file. `.tmp/sessions/` does not exist yet and does not need to — the next run creates it, which
was verified rather than assumed:

```
$ python scripts/mutation.py --gate
BLOCKED: no record in .../.tmp/sessions answers for the corpus — the session has not run

$ python scripts/mutation.py --corpus-dir .../TECH-049 --out .tmp/verify_sessions
record: .tmp/verify_sessions/2026-08-27T10-03-36.553982-00-00_full.json
```

The gate says the right thing about an absent store, and a run rebuilds one. The verification
artefacts were then removed too.

## A trap this walked into

`cd .tmp && find . -delete` worked, and the **next** command was still in `.tmp`. The shell's
working directory persists between calls, so `wc -l .tmp/HANDOVER.md` resolved to
`.tmp/.tmp/HANDOVER.md` and reported the handover missing — for about ten seconds it looked like
the sweep had eaten the one file it was told to keep.

It had not. But trap 2 in `working_in_this_repo.md` is about exactly this class — a relative path
that breaks the moment anything `chdir`s — and it arrived from a direction that guide does not
cover: not a test creating a worktree, just two shell calls in a row. **Absolute paths for anything
that deletes.**

## Why this stays a one-off and does not become a rule

`.tmp/` gets no automatic prune, deliberately `[agreed 2026-08-27]`. An unattended delete on a
gitignored directory removes evidence nobody can review, and this repo has already lost a month of
handover that way. The session store has a rule because its records carry a **state** — a failure
is kept until a clean run supersedes it — and the rest of `.tmp/` carries none.

The replacement for a rule is that the store now says when it is growing: the run and `--gate` both
warn past 20 unsuperseded records.

## Results

| Check | Result |
|---|---|
| `.tmp/` | 68 files → **1** |
| full suite | unchanged — nothing in `.tmp/` is read by anything |
| `quality.py cb` / `doc` | green |

## The seven boundaries, closed

| | What it fixed |
|---|---|
| CB-1 | The gate could not read the record it is given; four ways of learning nothing read as CLEAR |
| CB-2 | A citation could name a requirement no design declares; `3 of 1 requirement(s)` |
| CB-3 | A scoped run withdrew every finding it never looked at |
| CB-4 | A record answered for less than it claimed, over a tree that was gone |
| CB-5 | One record path meant the last writer won |
| CB-6 | The store keeps a failure until it is fixed |
| CB-7 | The scratch nothing had ever pruned |
