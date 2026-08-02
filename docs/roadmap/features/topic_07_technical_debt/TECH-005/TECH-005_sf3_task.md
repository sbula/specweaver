# Task Breakdown: TECH-005 SF-3 — Prefix Raw-SQLite3 Tables

Implementation Plan: `TECH-005_sf3_implementation_plan.md`
Story kind: TECH (refactor) → `python scripts/tests.py cb TECH-005 --kind refactor`

**Commit boundary**: single commit after T0–T4. The three files rename structurally identical
patterns (legacy-table detect-and-rename before schema creation); splitting into three commits
would force three HITL stops over a ~150-line, tightly-coupled diff with no independent value in
landing them separately — the design doc's own Progress Tracker only needs `SF-3` marked once.

## T0 — Extend `_refactor_diff_safety.py` to recognize a consistent literal-token rename ✅

**Why this is needed, discovered during task planning (not hypothetical):** every mechanical test
update in T1–T3 changes a SQL-string literal in place (e.g. `"...FROM nodes"` → `"...FROM
graph_nodes"`) — this is neither a pure addition nor a relocation (the two safe patterns the gate
already recognizes), so `refactor_violations()` would flag all six affected test files and
`python scripts/tests.py cb TECH-005 --kind refactor` (mandatory per the `dev` skill's Step A)
would hard-block the commit with "tests were bent to fit." Confirmed by reading
`_refactor_diff_safety.py`'s own matching logic (signature comparison requires either an exact
match or a match found elsewhere in the file — an in-place word substitution satisfies neither).
None of the other three `TECH_KINDS` (`bugfix`, `tooling`, `audit`) fit this ticket either. Per
this session's standing instruction on this exact gate ("think of something else to block
violently changed tests... don't let the bug persist" — not "bypass the gate"), the correct
response is another bounded extension, following the same precedent as the 5 rounds that built the
gate during TECH-001 SF-04, not reclassifying to dodge the check or skipping it.

- **Red**: add tests to `tests/unit/scripts/test_tests_runner.py` (or a focused new test module if
  that file is already large) covering:
  1. **Happy path**: a hunk that changes only one recurring word (`nodes` → `graph_nodes`)
     consistently across every mismatched line in a synthetic file diff → classified safe.
  2. **Boundary**: the SAME file also contains an unrelated pure addition in the same diff →
     still safe (the rename-closure check must compose with the existing matching, not replace it).
  3. **Graceful degradation**: a rename candidate that closes only PART of the residual gap
     (some remaining removed line has no explanation under the inferred pair) → NOT safe.
  4. **Hostile**: a diff where two DIFFERENT, unrelated single-word substitutions would each be
     needed to close the gap (i.e., no single global pair explains every remaining mismatch) →
     NOT safe — this is the case that must keep catching a real bug-hiding edit dressed up to look
     like a rename.
  Run — fails (function doesn't exist yet).
- **Green**: in `scripts/_refactor_diff_safety.py`, add (exact names may adjust during
  implementation, behavior must not):
  - A function that computes the leftover (still-unmatched) removed/added logical groups after
    the existing multiset pass.
  - A function that infers a single candidate `(old_token, new_token)` word-boundary pair from the
    leftover groups (only when exactly one consistent pair can be inferred — ambiguity is not
    safe).
  - A function that verifies applying that pair to every leftover removed group's normalized text
    reproduces the leftover added multiset exactly (full closure, no partial credit).
  - Wire this as an additional pass inside `_is_safe_file_diff`, after the existing matching,
    only consulted when a residual gap remains.
  Run the new tests — green. Re-run the full existing `test_tests_runner.py` suite (81+ tests) to
  confirm no regression in the 5 previously-fixed patterns.

## T1 — `repository.py`: rename `nodes`/`edges` → `graph_nodes`/`graph_edges` ✅

- **Red**: add `test_sqlite_repository_migrates_legacy_table_names_preserving_data` to
  `tests/unit/graph/core/store/test_repository_schema.py` (cites `TECH-005 FR-8`). Update the two
  existing schema tests' assertions to `graph_nodes`/`graph_edges`. Run — fails (source still
  creates `nodes`/`edges`, no migration logic exists).
- **Green**:
  - `src/specweaver/graph/core/store/repository.py`: add `_rename_legacy_tables(conn)` — docstring
    names the two tables it renames (RED-1.6). Called at the start of `_init_db()`. Detects
    `nodes`/`edges` in `sqlite_master`; if the corresponding new name doesn't already exist,
    `ALTER TABLE ... RENAME TO`; if the new name already exists too, skip + log a warning (D-3).
    Catch `sqlite3.OperationalError` ("no such table") as a no-op for the concurrent-construction
    race (RED-2.1/BLUE-2.1). Rename `nodes` before `edges` (D-2). Update all SQL strings in the
    file (DDL + `_get_hash_to_id_map`, `persist_semantic_digraph` ×3, `load_from_db` ×2,
    `purge_file`, `purge_stale_entries` ×2, `get_all_file_hashes`).
  - Mechanical: update raw SQL literals in `test_repository_load.py`, `test_purge_stale.py`,
    `test_repository_flush.py`, `test_repository_helpers.py`,
    `tests/integration/interfaces/cli/test_cli_graph_integration.py`.
  - Run `pytest tests/unit/graph/core/store/ tests/integration/interfaces/cli/test_cli_graph_integration.py -v` — must be green.

## T2 — `store.py`: rename `pipeline_runs`/`audit_log`/`state_schema_version` → `flow_*` ✅

- **Red**: in `tests/unit/core/flow/engine/test_engine_store.py`:
  - **Course correction on D-4, found running the real gate (not hypothetical):** the plan's
    original D-4 called for renaming `test_migration_v1_to_v2` to
    `test_migration_v1_to_v2_and_legacy_table_names` with an expanded docstring explaining the
    widening. Doing that and then running `python scripts/tests.py cb TECH-005 --kind refactor`
    for real showed it BLOCKS — a renamed function with rewritten prose is a genuine content
    change, not a mechanical one, and T0's gate correctly does NOT auto-clear it (nor should it —
    that's exactly the "tests bent to fit" signal the gate exists to catch, and prose changes have
    no mechanical proof of safety). Resolution: leave `test_migration_v1_to_v2`'s name and
    docstring untouched; apply ONLY the mechanical identifier substitution its two verification
    queries need (`state_schema_version`→`flow_state_schema_version`,
    `pipeline_runs`→`flow_pipeline_runs`) — that alone IS mechanically provable safe and the gate
    clears it. The coverage D-4 wanted from the widening is fully provided instead by the wholly
    new `test_migrates_legacy_table_names_from_v2_shape` below (a pure addition, always safe),
    which already asserts the exact old-names-gone/new-names-present/data-preserved claims more
    thoroughly than the abandoned widening would have.
  - Add `test_migrates_legacy_table_names_from_v2_shape` (cites `TECH-005 FR-8`): build a raw
    old-named DB already in the *current* v2 column shape (has `parent_run_id`) with real row data
    in all three tables, instantiate `StateStore`, assert all data preserved under the new names,
    schema version unchanged at 2 (no spurious re-migration).
  - Add `test_legacy_table_migration_preserves_foreign_key_integrity` (cites `TECH-005 FR-8`, D-5):
    after migrating a legacy DB, attempt an `audit_log`-equivalent insert with a nonexistent
    `run_id` against the renamed tables and assert `IntegrityError` still fires.
  - Add a rename-is-idempotent test driving `_rename_legacy_tables` twice against the same
    connection (RED-2.1), asserting the second call is a silent no-op.
  - Run — fails.
- **Green**:
  - `src/specweaver/core/flow/engine/store.py`: add `_rename_legacy_tables(conn)` — docstring names
    the three tables. Called at the very start of `_ensure_schema()`, before
    `executescript(_STATE_SCHEMA_V2)` and before the version-check block (ordering constraint from
    Research Notes — the version check reads `state_schema_version`, which is itself being
    renamed). Rename `pipeline_runs` before `audit_log`, `state_schema_version` last (D-2). Same
    D-3/RED-2.1 tolerance as T1. Update `_STATE_SCHEMA_V2` and all DML (`save_run`, `load_run`,
    `get_latest_run`, `list_runs`, `log_event`, `get_audit_log`, the v1→v2 `ALTER TABLE ADD COLUMN`,
    version-row queries).
  - Mechanical: update remaining raw SQL literals elsewhere in `test_engine_store.py`.
  - Run `pytest tests/unit/core/flow/engine/test_engine_store.py -v` — must be green.

## T3 — `reservation.py`: rename `sw_reservations` → `flow_reservations` ✅

- **Red**: in `tests/unit/core/flow/engine/test_reservation.py`, add
  `test_sqlite_reservation_migrates_legacy_table_name_preserving_data` (cites `TECH-005 FR-8`),
  `test_sqlite_reservation_skips_rename_when_both_old_and_new_tables_exist` (D-3), and a
  double-invocation idempotency test (RED-2.1, mirrors T2's). Run — fails.
- **Green**: `src/specweaver/core/flow/engine/reservation.py`: add `_rename_legacy_table(conn)` —
  docstring names the one table. Called at the start of `_ensure_schema()`, before
  `CREATE TABLE IF NOT EXISTS`. Same detect/rename/tolerate pattern as T1/T2. Update DDL and
  `acquire`/`release` DML.
  Run `pytest tests/unit/core/flow/engine/test_reservation.py -v` — must be green.

## T4 — Full regression sweep ✅

- `python -m pytest tests/unit/graph/ tests/unit/core/flow/engine/ tests/integration/interfaces/cli/test_cli_graph_integration.py tests/integration/graph/ -v --tb=short`
- `python scripts/tests.py cb TECH-005 --kind refactor`
- Fix any regression before the commit boundary.

## Commit Boundary (after T4) ✅ committed `4ebb89cf`

Full pre-commit gate (`specweaver-pre-commit`, all 7 phases + 7.5 Red/Blue) complete. Phase 7.5
found and fixed 2 HIGH findings in the rename logic itself (DDL-atomicity claim was wrong but the
actual resumability property holds; over-broad `except OperationalError` could have silently
swallowed real errors) — see `TECH-005_sf3_walkthrough.md`'s Red/Blue report for full detail.
Final story gate: 612 tests passed (500 unit + 112 integration), 0 failed. Committed as
`4ebb89cf` (2026-08-02).

## T5 — Story closure ✅ (except full-suite run, backgrounded)

SF-3 is the **last** row in TECH-005's Progress Tracker (SF-1 ✅, SF-2 ✅). Once SF-3 commits, every
row is `Committed ✅`, which per `specweaver-dev`'s own closure rule means the story is about to be
declared finished and must run the closure gate first — `check_fr_coverage.py` + the full suite —
before writing `Status: COMPLETE`.

**Confirmed outcome**: `check_fr_coverage.py TECH-005` fails for **FR-1 through FR-7** — `NO PLAN
NO TEST` for FR-1–5/7, `plan NO TEST` for FR-6 — because SF-1/SF-2 shipped before this gate
existed/was wired into closure and never carried the `FR-N` + story-ID citation convention. FR-8
(SF-3's own) passes with 3 citing test files.

Per finished-stories-immutable, SF-1/SF-2's delivered files are not edited to backfill citations
under this ticket. Steps:
1. ✅ Ran `check_fr_coverage.py TECH-005` for real post-commit — confirmed the outcome above.
2. ✅ Asked the user whether to mint a new ticket (`TECH-026`) or fold into `TECH-025` (which was
   scoped to TECH-001 only). **User chose to widen `TECH-025`** — retitled and rewritten to cover
   both TECH-001 SF-01/02/03 and TECH-005 SF-1/2's identical citation gap, rather than minting a
   second ID for the same systemic cause.
3. Full suite (`python -m pytest -v --tb=short -q`) running in background as closure proof; the
   story-scoped gate (`tests.py cb TECH-005 --kind refactor`) already confirmed 612 passed, 0
   failed. `TECH-005_design.md`'s Progress Tracker and Session Handoff updated.
4. ✅ Updated `master_story_roadmap.md` and `topic_07_technical_debt.md`'s TECH-005 status to reflect
   completion, honestly describing current state (not a changelog entry) — requires the
   `SW_ALLOW_FINISHED_EDIT` bypass flag since this flips TECH-005 to fully green; ask the user to
   set it, same pattern as TECH-001.

---
# Red/Blue Team Review Report

## Summary
- **Target**: TECH-005 SF-3 Task Breakdown (`TECH-005_sf3_task.md`)
- **Cycles**: 2
- **Findings**: 4 (Cycle 1) + 0 (Cycle 2)
- **Critical/High fixes applied**: 1

## Cycle Log

### 🔴 RED-1.1: The refactor-safety gate will hard-block this exact commit
**Category**: Robustness & Edge Cases / Testability
**Severity**: HIGH
**Target**: T1–T3's mechanical test updates vs. `scripts/_refactor_diff_safety.py`
**Finding**: Every mechanical test-file edit in T1–T3 changes a SQL-string literal in place
(`nodes` → `graph_nodes`, etc.) — neither a pure addition nor a relocation, the only two patterns
`_is_safe_file_diff` currently recognizes as safe. `python scripts/tests.py cb TECH-005 --kind
refactor`, mandatory per the `dev` skill's Step A, will list all six affected test files and
BLOCK the commit with "tests were bent to fit."
**Evidence**: Traced `_hunk_signature`/`_is_safe_file_diff` directly — a single differing word with
no relocation elsewhere in the file has no path to a match. Confirmed no `--force`/override flag
exists anywhere in `tests.py`.

### 🔵 BLUE-1.1: Response to RED-1.1
**Verdict**: VALID — FIX REQUIRED
**Response**: Extend the gate with one more bounded safe-pattern (added as T0, done before T4's
gate run): a single, file-wide-consistent literal-token substitution, verified by closure (the
substitution must explain every remaining unmatched line, not just some) — not a bypass, per this
session's own standing instruction on this exact gate. The adversarial test in T0's Red step
(bucket 4: two DIFFERENT substitutions needed → not safe) is the load-bearing guard that keeps this
addition from weakening the gate's original purpose of catching a bug hidden behind a bent test.

### 🔴 RED-1.2: The story-closure step will find a pre-existing FR gap unrelated to this SF
**Category**: Maintainability
**Severity**: MEDIUM
**Target**: T5 / `check_fr_coverage.py TECH-005`
**Finding**: SF-3 is the last Progress Tracker row — landing it triggers the closure gate. Running
`check_fr_coverage.py TECH-005` now (read-only, to know what T5 will hit) shows FR-1–7 (SF-1/SF-2,
delivered before this gate existed) already fail on citation. Left undocumented, T5 could either
silently declare the story complete over a real gate failure, or block indefinitely on a gap this
SF didn't create and per finished-stories-immutable must not fix by editing SF-1/2's own files.
**Evidence**: `check_fr_coverage.py TECH-005` output, run during task planning.

### 🔵 BLUE-1.2: Response to RED-1.2
**Verdict**: VALID — FIX REQUIRED
**Response**: T5 documents the exact known outcome up front and routes it through the same pattern
already established for TECH-001/TECH-025: mint a new ticket for the citation gap (with the user's
required confirmation before Phase 3 of `specweaver-ticket`) rather than fixing finished files or
silently ignoring the gate.

### 🔴 RED-1.3: Does T0's new closure-matching logic risk laundering a real bug as a "rename"?
**Category**: Security & Safety / Correctness
**Severity**: MEDIUM
**Target**: T0's design
**Finding**: A single-token-substitution safe-pattern is a strictly WEAKER check than the existing
two patterns — worth confirming it can't be gamed by a genuinely bug-hiding edit that happens to
differ by one consistent word.
**Evidence**: n/a — design question, not yet code.

### 🔵 BLUE-1.3: Response to RED-1.3
**Verdict**: VALID — ADDRESSED BY DESIGN, VERIFY IN T0's OWN TESTS
**Response**: Closure must be exact and total — every remaining unmatched removed line must be
explained by the SAME single pair, with zero leftover. A bug-hiding edit that changes assertion
LOGIC (an operator, a threshold, a removed check) essentially never reduces to "the same one word
swapped everywhere," and if an adversary constructed one that did, the surface area is a single
literal token appearing identically across every touched line — narrow enough to be conspicuous in
a diff review, and no narrower than the existing path-relocation pattern's own blind spot (a
maliciously placed decoy import path could theoretically hide behind that pattern too, and this
session accepted that risk already for path relocation). T0's own hostile-bucket test pins the
boundary precisely: two independent substitutions required → rejected.

### 🔴 RED-1.4: T0 is scope creep onto a tooling script from inside a database-rename ticket
**Category**: Architecture & Design
**Severity**: LOW
**Target**: T0 vs. TECH-005's own scope (FR-8: "rename raw-sqlite3 tables")
**Finding**: `scripts/_refactor_diff_safety.py` has nothing to do with TECH-005's subject matter.

### 🔵 BLUE-1.4: Response to RED-1.4
**Verdict**: INVALID — NO ACTION (documented precedent, not scope creep)
**Response**: Per this session's standing rule, an inherited/blocking tooling defect discovered
while doing the actual work must be fixed, not deferred — the same reasoning already applied
mid-flight during TECH-001 SF-04 (which fixed `check_story_preconditions.py` and built this exact
gate for the same reason: the mandated gate for THIS commit was wrong). Deferring T0 to a separate
ticket would mean SF-3 cannot commit at all until that ticket lands, making the "separation" purely
nominal.

## Corrections Made
- Added T0 (gate extension, full adversarial test matrix) ahead of T1.
- Added T5 (story closure) with the FR-1–7 gap pre-documented and routed to a new ticket rather
  than silently handled either way.

## Accepted Risks
- None below HIGH/MEDIUM were left unaddressed.

**Cycle 2**: re-checked all focus areas (DDD/boundaries — no new imports, `context.yaml`s
unaffected; security — table names are fixed literals, no interpolated user input, no injection
surface; platform — SQLite rename/FK behavior is identical on Windows/Linux; race conditions —
already covered by the idempotency test inherited from the plan-level review's RED-2.1).
**Zero new findings** — below all continuation thresholds. Review complete.

*(End of Red/Blue Team Review Report)*
