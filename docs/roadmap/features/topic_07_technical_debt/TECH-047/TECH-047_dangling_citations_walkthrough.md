# Walkthrough: `TECH-047` — the FR ledger ran in one direction only

- **Ticket**: none, by the `TECH-049 FR-11` precedent. The record is this file, the test
  docstrings, a new section in `TECH-047_design.md`, and 9 fixed citations
- **Kind**: tooling · **DAL-C** · 2026-08-27 · **CB-2 of 7**

## The failure

`check_fr_coverage.py` asked *is every declared FR cited by a test*. It never asked the reverse:
*does every citation name a declared requirement*.

So a `Proves:` tag could credit evidence to a requirement that does not exist — and a tag naming
nothing reads exactly like a tag naming something. `TECH-056` declares **one** FR and says so in
its own prose:

> **One requirement.** The `runs` counter is not a second one.

A test carried `Proves: TECH-056 FR-2`. The checker printed:

```
1 FR(s) declared in TECH-056_design.md: FR-1
4 FR(s) cited by tests naming TECH-056
3 of 1 requirement(s) carry an authoritative `Proves:` tag
```

**`3 of 1`.** A ratio above its own denominator, on screen every time anyone ran the tool, exit
code 0.

## Measuring it, and getting it wrong first

The first pass compared every citation against the **FR table** and reported **70** dangling ids
across 29 stories. That number is wrong: 62 of them are `NFR-N`, declared perfectly well in the
**NFR** table, which `declared_frs` does not read.

A check that is 89% false positives is one nobody reads. Against both tables the answer is **10**,
of which 2 are the documented `FR-98`/`FR-99` fixture convention — so **9 real ones, 6 stories**.

Trap 3 in `working_in_this_repo.md`, arriving exactly as written: a surprising measurement was
first evidence that the measurement was wrong.

## What the 9 turned out to be

| Citation | Diagnosis |
|---|---|
| `INT-US-24 FR-9`, `FR-10` | fixture strings fed to the parser under test — moved above the floor |
| `INT-US-09 NFR-8` ×2 | `# NFR-8:` comment prefixes; the design declares `NFR-1..7` |
| `INT-US-24 NFR-8` | comment prefix; the design declares `NFR-1..5` |
| `TECH-020 NFR-4` | that design has **no requirements section at all** |
| `TECH-065 NFR-2` | a stale sentence about skipping Java logic on Python files; no NFR table |
| `A-VAL-01 FR-6` | see below |
| `TECH-058 FR-2`, `FR-3` | **real behaviour the design never declared** — see below |

**`A-VAL-01 FR-6` is the one that proves the class matters.** The citing file's docstring already
*explains* the defect — a cross-story text scan inventing an id — and in explaining it spells the
qualified string `A-VAL-01 FR-6`, which re-creates it. Somebody diagnosed this by hand, wrote a
paragraph, and nothing has caught it since.

It then happened to me: the comment I wrote explaining the `INT-US-24` fixture fix named the
offending id and the next sweep caught it. **Twice in one boundary**, which is the argument for
the check in one line.

## `TECH-058` gained two requirements

Its table held `FR-1` — *the baseline runs the suite in parallel*. Two test classes claimed more,
and both are real, shipped, and load-bearing:

- `TestTimerUnitsCarryAUsablePath` — without `.venv/bin` on the unit's `PATH`, `tach` is missing,
  collection errors, and the baseline goes red **naming no failing test**. That is the shape that
  read as four flaky nights in August.
- `TestTimerUnitsRaiseTheFileDescriptorLimit` — without `LimitNOFILE`, `-n auto` exhausts the 1024
  a user service inherits, as ~690 `OSError`s across unrelated tests that fail in no single tier.

The ticket delivered three things and the table claimed one. `FR-2` and `FR-3` added
`[agreed 2026-08-27]`, and the plan's `FRs owned` line now names what its own boundary shipped.

## The fix

| # | Change |
|---|---|
| 1 | `dangling_citations()` in `check_fr_coverage.py` — both tables, minus the fixture floor |
| 2 | `main()` blocks on it, with a message that separates the two repairs: a typo in the test, or a row the design lost |
| 3 | `check_dangling_citations.py` sweeps **every** design in the `doc` gate. `development_framework.md`: a check that must be invoked to fire reports success by not running — and 2 of the 9 were on a story closed months ago |
| 4 | The rule lives once. The sweep imports `dangling_citations`; a test pins that they are the same object |
| 5 | `FIXTURE_ID_FLOOR = 90` `[agreed 2026-08-27]`, a property of the id rather than of the file — the existing `fixture-data` marker is file-level and would discard that file's real citations too |
| 6 | The ratio's numerator is intersected with the declared FRs, so it can no longer exceed its denominator |

## Probes

Scoped to `test_check_fr_coverage.py` and `test_check_dangling_citations.py`.

| Neutralised | Objections |
|---|---|
| the NFR table is ignored | 2 |
| the fixture floor is removed | 2 |
| `FIXTURE_ID_FLOOR = 0` — everything is a fixture | 7 |
| a dangling citation does not block | **1** (was **SILENT** — see below) |
| the ratio uses the old numerator | **1** |
| a sweep that examined nothing passes | **1** |

**One mutant was SILENT, and it caught a vacuous test of mine.**
`test_main_blocks_on_a_dangling_citation` asserted `code == 1` — and passed with the dangling rule
deleted, because the fixture story had **no implementation plan**, so `missing_from_plan` blocked
it regardless. The test proved the wrong rule. Its fixture now writes a plan, and the assertion
requires the other two failure messages to be *absent*, so only the dangling rule can be what
blocked. The mutant objects now.

A guard that cannot fail is not a guard, and 3.2b is the only thing that found this one.

## Results

| Check | Result |
|---|---|
| full suite | **9,001 passed, 11 skipped** in 90s (was 8,986) |
| `quality.py cb` | 14 passed, 1 skipped, 0 failed |
| `quality.py doc` | **14** passed, 0 failed — the new sweep is the fourteenth |
| `check_dangling_citations.py` | 139 designs swept, 0 findings |
| `check_fr_coverage.py TECH-058` | every declared FR planned and cited |

## Not fixed here, and named

- **`INT-US-24` and `INT-US-09` still fail the forward ledger** — `FR-5` and `FR-1/3/4/5` cited by
  no test. **Identical at `HEAD`**, checked by stashing: pre-existing, part of the delivered-but-
  unproven backlog `TECH-047` itself scoped out, not caused here.
- **The two `TECH-058` citations are `[legacy]`, not `[Proves:]`.** `strict_citations` reads the
  **module** docstring only and those tags are on classes. Working as designed; the legacy column
  is the one to drain, and draining it is not this boundary.
- **`check_dangling_citations.py` has no mutants in the durable corpus.** It belongs to
  `TECH-047`, which has no `_mutants.json` and no FR table to scope a campaign against. The probes
  above are recorded here instead; giving `TECH-047` a requirement table is a design change and
  was not asked for.
