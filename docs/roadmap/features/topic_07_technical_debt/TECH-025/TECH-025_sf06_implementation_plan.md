# Implementation Plan: Registry IDs Leaking Into Proofs [SF-06: TECH-005 FR Ledger]

- **Feature ID**: TECH-025
- **Sub-Feature**: SF-06 — TECH-005 FR Ledger
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-06
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf06_implementation_plan.md
- **Status**: APPROVED (user, 2026-08-12 — all three Phase-4 recommendations taken)

> Bare `FR-N` below means **TECH-025's** requirement. TECH-005's are always written qualified —
> `TECH-005 FR-4`. This plan is about FR numbering, so the qualification is not optional.

## Overview

`check_fr_coverage.py TECH-005` exits 1. Of its eight requirements, **FR-8 is already closed** — SF-03
delivered it in 2026-08-02 with three genuine citations. This sub-feature closes the other seven.

**FRs**: FR-3 (close TECH-005's ledger).

The substance is not in doubt. The renames shipped, the migration ran, and SF-03 already extended the
work to the six raw-sqlite3 tables. This is traceability.

## Research Notes

**R1 — Ownership is clean, and one of the eight is done.**

| TECH-005 SF | Owns | State |
|---|---|---|
| SF-01 Model Refactoring | `FR-1`…`FR-5` | delivered, uncited |
| SF-02 Alembic Migration | `FR-6`, `FR-7` | delivered, uncited |
| SF-03 Prefix Raw-SQLite3 Tables | `FR-8` | **closed** — 3 citations |

**R2 — `FR-6`'s current "plan" status is spurious, and it is the plan-side twin of SF-05's trap.**
The gate reports `TECH-005 FR-6` as planned. Nothing owns it: the token appears in **SF-03's** plan
(`TECH-005_sf03_implementation_plan.md:26`) inside the sentence *"SF-02/FR-6, there is no
index-rename sub-task here"* — a cross-reference explaining what SF-03 does **not** do.
`planned_frs` unions every plan's tokens without asking which sub-feature claims them, so a
disclaimer reads as ownership.

SF-05's Red/Blue found the same shape on the test side. Same lesson: **verify by which document
owns the requirement, not by whether the token appears somewhere.**

> Checked, and it is only this one. `NFR-1` at `sf03:37` does **not** leak into `FR-1` — the gate's
> `(?<![\w-])(FR-\d+)` lookbehind rejects the preceding `N`, which a plain grep does not. The gate
> is more precise than the obvious search; do not "fix" a finding a grep reports here without
> re-checking it through `collect_frs`.

**R3 — Test-side reality: five of seven have a genuine proof, two have nothing.**
Every file below was read, not name-matched.

| TECH-005 FR | Claim | Existing proof | Verdict |
|---|---|---|---|
| FR-1 | Rename workspace tables | `tests/unit/alembic/test_table_prefix_migration.py::test_upgrade_renames_tables_and_indexes` — asserts the `op.rename_table` calls | **Genuine** |
| FR-2 | Rename flow tables | same test | **Genuine** |
| FR-3 | Rename llm tables | same test | **Genuine** |
| FR-4 | Update `__tablename__` in models | — | **None** |
| FR-5 | Update raw SQL + string FKs | — | **None** |
| FR-6 | Rename indexes | same test — the index half of its assertions | **Genuine** |
| FR-7 | Generate the Alembic migration | `::test_live_sqlite_migration` — runs the real revision against a real SQLite file | **Genuine** |

**R4 — Both absent claims verified TRUE against the live tree (2026-08-12), before planning to
assert them.** A test written against a false claim is worse than no test.

- **FR-4**: every table across all four declarative bases carries a bounded-context prefix —
  `llm_*` (4), `workspace_*` + `memory_*` (8), `flow_*` (1). Zero unprefixed.
- **FR-5**: no legacy name (`projects`, `active_state`, `project_standards`, `artifact_events`,
  `project_llm_links`) appears after `FROM`/`INTO`/`UPDATE`/`TABLE`/`JOIN` anywhere in
  `src/specweaver/`.

**R5 — Credit safety: every target is clean.** Checked before choosing them —
`test_table_prefix_migration.py` names no story and carries no requirement token, so tagging it
credits TECH-005 exactly the tokens this plan adds and nothing else. The same check killed SF-05's
original file choice, so it is done first here rather than last.

**R6 — The three files already citing `TECH-005 FR-8` must not be reused.**
`test_repository_schema.py`, `test_engine_store.py` and `test_reservation.py` name TECH-005 and
carry `FR-8`. Adding an `FR-4` token to any of them would work, but it would attach a requirement
about SQLAlchemy models to tests about raw-sqlite3 tables — true by the gate, false to a reader.
The new invariants get their own file.

**R7 — A registry ID in a shipped filename, recorded not fixed.**
`alembic/versions/af60fd3509a2_tech_005_rename_tables.py` carries a story ID. `check_conventions`
R5 covers test names only, so this is not a violation today, and renaming an applied Alembic
revision is a migration-history change, not a rename. **Out of scope; recorded for `TECH-027`**,
which owns identifier contracts.

## Proposed Changes

### 1. Plan-side citations (7 requirements, 2 plans)

| Plan | Add | Note |
|---|---|---|
| `TECH-005_sf01_implementation_plan.md` | `FR-1`…`FR-5` | |
| `TECH-005_sf02_implementation_plan.md` | `FR-6`, `FR-7` | makes `FR-6`'s ownership real rather than inherited from R2's disclaimer |

`sf03` is untouched — it owns `FR-8` and already cites it. Each plan gains a dated note naming
`TECH-025` as author under AD-4. No plan gains scope.

### 2. Test-side citations (5 existing proofs, 1 file)

A single `Proves: TECH-005 FR-N.` line per test docstring in
`tests/unit/alembic/test_table_prefix_migration.py`:

- `test_upgrade_renames_tables_and_indexes` → FR-1, FR-2, FR-3, FR-6
- `test_live_sqlite_migration` → FR-7

Per-test rather than one module tag, matching SF-05's Q3 decision and `TECH-006`'s precedent:
deleting a test then visibly drops its citation.

### 3. `[NEW] tests/unit/test_table_naming_convention.py` — two invariants

Written test-first. Names **only** `TECH-005` and carries exactly two requirement tokens, with a
self-guard asserting both — SF-05's file paid for that guard twice and it is cheap to carry.

| For | Asserts |
|---|---|
| TECH-005 FR-4 | Every `__tablename__` across the four declarative bases starts with a bounded-context prefix |
| TECH-005 FR-5 | No module under `src/specweaver/` references a legacy table name in raw SQL |

Needs its own real-tree guard: both are shaped like absence proofs, and SF-05 CB-1 established that
such a guard is **not** inherited from a sibling module.

## Test Plan

| # | Bucket | Story |
|---|---|---|
| T1 | Guard | The four bases actually load and register a non-empty table set — a base that imports to zero tables would pass FR-4 vacuously |
| T2 | Happy | Every registered table name carries a known bounded-context prefix (FR-4) |
| T3 | Happy | No legacy table name appears in raw SQL under `src/` (FR-5) |
| T4 | Hostile | A synthetic model with an unprefixed `__tablename__` is reported |
| T5 | Hostile | A synthetic module with `SELECT … FROM projects` is reported |
| T6 | Boundary | A *prefixed* name that merely contains a legacy substring (`workspace_projects` contains `projects`) is **not** reported — the check is on the referenced identifier, not a substring |
| T7 | Degradation | An unreadable/unparseable module raises rather than being skipped |
| T8 | Invariant | This file names one story and holds exactly two requirement tokens |
| T9 | Regression | `check_fr_coverage.py TECH-005` exits 0; TECH-001/002 stay 0; TECH-022 stays 1; INT-US-21/24 stay 0 |

T6 is the one most likely to be got wrong: a naive `"projects" in sql` matches `workspace_projects`
and reports the *fixed* name as a violation, which would make FR-5's test fail against a correct
tree.

## Verification

```bash
PY=.venv/bin/python
$PY -m pytest tests/unit/test_table_naming_convention.py tests/unit/alembic/ -v --tb=short
$PY scripts/check_fr_coverage.py TECH-005          # MUST exit 0 — this sub-feature's whole point
$PY scripts/check_fr_coverage.py TECH-001          # MUST stay 0
$PY scripts/check_fr_coverage.py TECH-002          # MUST stay 0 — SF-05 just closed it
$PY scripts/check_fr_coverage.py TECH-022          # MUST stay 1 — no new accidental credit
$PY scripts/quality.py cb
$PY scripts/tests.py cb TECH-025 --kind tooling --all
```

**Verify attribution by file list, not by exit code.** SF-05's Red/Blue established that a count
cannot distinguish a borrowed citation from a real one, because the ledger going green is the
declared goal. Each TECH-005 FR must resolve to the file that genuinely proves it.

`--all` is not optional: the default profile for a tooling-kind TECH ticket selects the unit tier
only, and the closure check must see all three.

## Commit Boundaries

**CB-1 — the two new invariants.** T1–T8. Ledger stays RED: this boundary answers *is the claim
true?*

**CB-2 — citations and the plan-side ownership repair.** Turns the ledger green, and answers *is it
linked?*

> Same split as SF-04 and SF-05, for the same reason: doing both at once makes a real proof
> indistinguishable from a tag.

## Open Questions for the Phase 4 Gate

| # | Question |
|---|---|
| Q1 ✅ | *Decided: text scan with word-boundary matching.* **Should FR-5's scan be an AST walk or a text scan?** The strings live in raw SQL inside Python string literals, so an AST walk finds them precisely but must handle f-strings and concatenation; a text scan is simpler and risks T6's substring trap. Recommend **text scan with word-boundary matching on the identifier**, since the thing being checked is a SQL identifier, not a Python expression. |
| Q2 ✅ | *Decided: leave the sentence; record the gate limit.* **Does `FR-6`'s spurious plan status (R2) need fixing beyond adding the real citation?** Adding `FR-6` to `sf02` makes ownership true, but SF-03's disclaimer sentence still contributes the token. Recommend leaving the sentence — it is correct prose — and accepting that `planned_frs` cannot distinguish. Worth recording against `TECH-025` SF-07 or `TECH-026`, since it is a gate precision limit, not a document defect. |
| Q3 ✅ | *Decided: the new file.* **Where do FR-4/FR-5's invariants live** — the new `test_table_naming_convention.py` as planned, or extended into `tests/unit/alembic/`? Recommend the new file: the alembic directory is about migrations, and FR-4/FR-5 are about the current tree, not a revision. |
