# Walkthrough: TECH-025 SF-06 CB-2 — the third ledger closes

- **Feature ID**: TECH-025 / SF-06 (TECH-005 FR Ledger)
- **Date**: 2026-08-12
- **Boundary**: CB-2 of 2

## Result

```
check_fr_coverage.py TECH-005  ->  exit 0
  8 FR(s) declared · 3 implementation plan(s) · 8 FR(s) cited by tests
```

**All three subject ledgers are now closed** — `TECH-001` (SF-04), `TECH-002` (SF-05),
`TECH-005` (here). That was the substantive goal of the whole ticket; SF-07's manifest exists to
stop them reopening.

## What changed

| File | Change |
|---|---|
| `TECH-005_sf01_implementation_plan.md` | FR-1…FR-5, under AD-4, with a dated note |
| `TECH-005_sf02_implementation_plan.md` | FR-6, FR-7, plus the R2 note below |
| `test_table_prefix_migration.py` | Per-test tags — the mocked upgrade test → FR-1/2/3/6, the live SQLite test → FR-7 |

`sf03` untouched: it owns FR-8 and already cites it.

## The plan-side twin of SF-05's trap

`FR-6` was already reported as **planned** before this boundary, and nothing owned it. The token
appeared only in **SF-03's** plan, inside a sentence explaining that SF-03 has *no* index-rename
sub-task. `planned_frs` unions every plan's tokens without asking which sub-feature claims them, so
a disclaimer read as ownership.

SF-05 found the same shape on the test side; this is its plan-side counterpart. The citation added
to `sf02` makes the ownership real, and the note records why the status was already green.

> A related trap avoided: a plain grep also "finds" `FR-1` in that file, but it is inside `NFR-1`.
> The gate's `(?<![\w-])(FR-\d+)` lookbehind rejects the preceding `N`. **The gate is more precise
> than the obvious search** — a finding from grep must be re-checked through `collect_frs` before
> anyone acts on it.

## Verified by attribution, not by exit code

```
FR-1  test_table_prefix_migration.py     FR-5  test_table_naming_convention.py
FR-2  test_table_prefix_migration.py     FR-6  test_table_prefix_migration.py
FR-3  test_table_prefix_migration.py     FR-7  test_table_prefix_migration.py
FR-4  test_table_naming_convention.py    FR-8  test_repository_schema.py + 2 others
```

Each resolves to the file that genuinely proves it. FR-1/2/3/6 share one file because one test
asserts all four renames in one call inventory — that is the shape of the proof, not a shortcut.

## No credit leaked

`test_table_prefix_migration.py` was checked before being chosen: no story ID, no requirement token.
The three modules already citing `TECH-005 FR-8` were deliberately **not** reused — they prove a
requirement about raw-sqlite3 tables, and attaching a SQLAlchemy-model requirement to them would be
true by the gate and false to a reader.

Ledgers after: `TECH-005` 0 (was 1) · TECH-001 0 · TECH-002 0 · TECH-022 1 · TECH-025 1 ·
TECH-006 0 · INT-US-21 0 · INT-US-24 0. Only the intended one moved.

## Gates

| Gate | Result |
|---|---|
| `check_fr_coverage.py TECH-005` | **exit 0** |
| Attribution by file list | 8/8 correct |
| `quality.py quick` | clean |
| unit / integration / e2e | 5604·1 / 578·13 / 182·9 — unchanged from CB-1 |

All 23 failures remain accounted for: 18 `TECH-029`, 4 Cluster E tooling, 1 `TECH-030` held red
deliberately. None is this boundary's and none moved.

## What remains for TECH-025

SF-07 only — the regression manifest and its guard. Its constraint is already recorded from SF-05's
Red/Blue: TECH-025's own ledger cannot simply tag the sub-feature test files, because each names a
subject story and carries that story's tokens.
