# Implementation Plan: Database Table Prefix Harmonization [SF-3: Prefix Raw-SQLite3 Tables]
- **Feature ID**: TECH-005
- **Sub-Feature**: SF-3 — Prefix Raw-SQLite3 Tables
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-005/TECH-005_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-005/TECH-005_sf3_implementation_plan.md
- **Status**: APPROVED

## Research Notes (Phase 0)

**Precondition check**: `python scripts/check_story_preconditions.py TECH-005` — PASSED (5 passed, 1
allowlisted warning for `workspace_roots`, 0 failures).

**The six tables and their owning files** (all confirmed via direct read, not grep):

| Old name | New name | File | FK relationships |
|---|---|---|---|
| `nodes` | `graph_nodes` | `src/specweaver/graph/core/store/repository.py:33` | referenced by `edges.source_id` |
| `edges` | `graph_edges` | same, `:47` | `source_id → nodes(id)` (no FK on `target_id` — lazy edges, intentional) |
| `pipeline_runs` | `flow_pipeline_runs` | `src/specweaver/core/flow/engine/store.py:33` | self-FK `parent_run_id → pipeline_runs(run_id)`; referenced by `audit_log.run_id` |
| `audit_log` | `flow_audit_log` | same, `:46` | `run_id → pipeline_runs(run_id)` |
| `state_schema_version` | `flow_state_schema_version` | same, `:55` | none |
| `sw_reservations` | `flow_reservations` | `src/specweaver/core/flow/engine/reservation.py:35` | none |

**No `CREATE INDEX` statements exist in any of the three files** (confirmed by full read) — unlike
SF-2/FR-6, there is no index-rename sub-task here.

**These are real, persistent, user-owned files, not test-only artifacts** — renaming is a genuine
data migration, not a code-only change:
- `graph.db` → `<project_path>/.specweaver/graph.db` (`graph/core/builder/orchestrator.py:190`)
- `pipeline_state.db` → `state_db_path()` = `$SPECWEAVER_DATA_DIR/pipeline_state.db` or
  `~/.specweaver/pipeline_state.db` (`core/config/paths.py:51`)
- `reservations.db` → `<project_path>/.specweaver/reservations.db` (`core/flow/engine/gates.py:109`)

A blind `CREATE TABLE IF NOT EXISTS <new_name>` on an existing installation would create an empty
new-named table alongside the old one, **silently orphaning every persisted graph, pipeline run,
and audit event** — this violates TECH-005's own NFR-1 ("Zero data loss") which SF-1/SF-2 satisfied
via Alembic's `op.rename_table` for the SQLAlchemy tables. SF-3 needs the raw-`sqlite3` equivalent:
`ALTER TABLE <old> RENAME TO <new>`.

**`store.py` already has a version-gated migration precedent** (`_ensure_schema()`: v1→v2 adds
`parent_run_id` via `ALTER TABLE ... ADD COLUMN`, gated on reading `state_schema_version`). The
table-rename must happen **before** that version check runs, because the version check itself
reads from a table that is also being renamed (`state_schema_version` →
`flow_state_schema_version`) — if the rename ran after, the version check would find `existing ==
0` on the new table and treat a real existing installation as brand new, re-inserting version 2
without ever running the v1→v2 column migration against the (still old-named) `pipeline_runs`
data.

**`repository.py` and `reservation.py` have no version-tracking table at all** — `_init_db()` /
`_ensure_schema()` are unconditional `CREATE TABLE IF NOT EXISTS`. Their legacy-rename check is
simpler: detect the old name in `sqlite_master`, rename if present, before the `CREATE TABLE IF NOT
EXISTS` for the new name (which then becomes a no-op on an already-renamed table, or creates fresh
on a brand-new DB).

**SQLite FK-reference auto-patching on rename**: `ALTER TABLE ... RENAME TO` has rewritten
FK-clause references to the renamed table in every other table's schema since SQLite 3.25.0
(2018) — this covers both `edges.source_id → nodes(id)` and `audit_log.run_id → pipeline_runs
(run_id)` (plus `pipeline_runs`'s own self-FK). Python 3.11's bundled `sqlite3`/libsqlite3 is far
newer than 3.25. Treated as a research fact, not assumed blindly — Test Plan includes a live
FK-integrity assertion post-rename rather than trusting this alone.

**Existing test inventory** (7 files touch these table names via raw SQL, all found by grepping for
`(FROM|INTO|UPDATE|TABLE|JOIN|REFERENCES)\s+(nodes|edges|pipeline_runs|audit_log|
state_schema_version|sw_reservations)\b` — a plain word-boundary grep on the bare names would have
produced 47 false positives from files using "nodes"/"edges" as generic graph vocabulary, not SQL
identifiers):
- `tests/unit/graph/core/store/test_repository_schema.py` — schema assertions (table names,
  column info via `PRAGMA table_info`)
- `tests/unit/graph/core/store/test_repository_load.py`
- `tests/unit/graph/core/store/test_purge_stale.py`
- `tests/unit/graph/core/store/test_repository_flush.py`
- `tests/unit/graph/core/store/test_repository_helpers.py`
- `tests/integration/interfaces/cli/test_cli_graph_integration.py`
- `tests/unit/core/flow/engine/test_engine_store.py` — also contains `test_migration_v1_to_v2`,
  which manually creates a **raw legacy DB using the current unprefixed table names** to test the
  v1→v2 column migration. Post-SF-3, that fixture *is* exactly the real-world legacy shape (old
  names, old column set) — repurposed rather than duplicated (see Resolved Decisions).
- `tests/unit/core/flow/engine/test_reservation.py` — uses only the public `acquire`/`release` API,
  no raw-SQL table-name literals; needs new tests added, no mechanical edits.

## Resolved Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| D-1 | Where does the rename logic live? | A private method on each of the three existing classes (`_rename_legacy_tables`/`_rename_legacy_table`), not a shared cross-file helper. | The three files sit in different `tach.toml` boundaries (`graph.core.store` vs. `core.flow.engine`) with no existing shared abstraction between them; a "shared SQL rename helper" module would be exactly the grab-bag-naming pattern the project's conventions forbid. Three ~10-line near-identical blocks is cheaper than a cross-domain dependency. |
| D-2 | Rename ordering within multi-table files | `repository.py`: rename `nodes` before `edges`. `store.py`: rename `pipeline_runs` before `audit_log`, `state_schema_version` last (least critical, no FK). | Matches existing `CREATE TABLE` declaration order; SQLite's FK-reference patching is schema-wide per statement, not order-dependent, but this keeps the diff readable and mirrors the DDL. |
| D-3 | What if both old and new names already exist (partial/corrupt prior migration)? | Detect via `sqlite_master`; if both present, skip the rename for that table, log a warning, and proceed (new-named table wins going forward). Do not raise, do not silently drop either table. | A hostile/corrupt-state input (adversarial matrix bucket 4) must degrade safely — refusing to start the whole application over one ambiguous table is worse than logging and continuing with the name every current code path already expects. A test pins this behavior. |
| D-4 | Extend `test_migration_v1_to_v2` or add a sibling? | Extend it in place (rename to `test_migration_v1_to_v2_and_legacy_table_names`, keep it building the raw legacy DB with old table names, assert final state uses new names) **and** add one new sibling test for the more common real case: an already-v2-shaped DB (has `parent_run_id`) that only has the old table names, with real row data, asserting the rename preserves that data exactly. | The v1 fixture already *is* an old-named table; changing only the assertions (not the fixture) turns an existing test into free coverage for the rename instead of a redundant new test. The v2-shaped case is the more common real installation and needs its own coverage since no existing test creates that combination. |
| D-5 | FK integrity after rename — trust the SQLite version guarantee, or test it? | Test it. Insert data before rename, trigger rename via the real constructor path, then attempt an FK-violating insert against the renamed tables and assert it still raises `IntegrityError`. | "The docs say 3.25+ handles this" is not the same as "this repo's bundled sqlite3 handles it" — direct proof per this session's standing rule against trusting claims without evidence. |

## Proposed Changes

| File | Change | FR |
|---|---|---|
| `src/specweaver/graph/core/store/repository.py` | Add `_rename_legacy_tables(conn)`, called at the start of `_init_db()` before the `CREATE TABLE IF NOT EXISTS` statements. Rename `nodes`→`graph_nodes`, `edges`→`graph_edges` in all SQL strings (DDL + 7 DML call sites: `_get_hash_to_id_map`, `persist_semantic_digraph` ×3, `load_from_db` ×2, `purge_file`, `purge_stale_entries` ×2, `get_all_file_hashes`). | FR-8 |
| `src/specweaver/core/flow/engine/store.py` | Add `_rename_legacy_tables(conn)`, called at the start of `_ensure_schema()` before `executescript(_STATE_SCHEMA_V2)` and before the version-check block. Rename `pipeline_runs`→`flow_pipeline_runs`, `audit_log`→`flow_audit_log`, `state_schema_version`→`flow_state_schema_version` in `_STATE_SCHEMA_V2` and all DML call sites (`save_run`, `load_run`, `get_latest_run`, `list_runs`, `log_event`, `get_audit_log`, plus the v1→v2 `ALTER TABLE` and version-row queries). | FR-8 |
| `src/specweaver/core/flow/engine/reservation.py` | Add `_rename_legacy_table(conn)`, called at the start of `_ensure_schema()` before the `CREATE TABLE IF NOT EXISTS`. Rename `sw_reservations`→`flow_reservations` in the DDL and the `acquire`/`release` DML. | FR-8 |
| `tests/unit/graph/core/store/test_repository_schema.py` | Update table-name assertions (`nodes`/`edges` → `graph_nodes`/`graph_edges`). Add `test_sqlite_repository_migrates_legacy_table_names_preserving_data` (cites `TECH-005 FR-8`). | FR-8 |
| `tests/unit/graph/core/store/test_repository_load.py` | Mechanical: raw SQL literals `nodes`/`edges` → `graph_nodes`/`graph_edges`. | FR-8 |
| `tests/unit/graph/core/store/test_purge_stale.py` | Mechanical, same substitution. | FR-8 |
| `tests/unit/graph/core/store/test_repository_flush.py` | Mechanical, same substitution. | FR-8 |
| `tests/unit/graph/core/store/test_repository_helpers.py` | Mechanical, same substitution. | FR-8 |
| `tests/integration/interfaces/cli/test_cli_graph_integration.py` | Mechanical, same substitution. | FR-8 |
| `tests/unit/core/flow/engine/test_engine_store.py` | Rename/extend `test_migration_v1_to_v2` (D-4). Add `test_migrates_legacy_table_names_from_v2_shape` and `test_legacy_table_migration_preserves_foreign_key_integrity` (cites `TECH-005 FR-8`). Mechanical substitution everywhere else (`pipeline_runs`→`flow_pipeline_runs`, `audit_log`→`flow_audit_log`, `state_schema_version`→`flow_state_schema_version`). | FR-8 |
| `tests/unit/core/flow/engine/test_reservation.py` | Add `test_sqlite_reservation_migrates_legacy_table_name_preserving_data` and `test_sqlite_reservation_skips_rename_when_both_old_and_new_tables_exist` (cites `TECH-005 FR-8`). | FR-8 |

No production call sites need changes — all six tables are only ever referenced by literal SQL
string inside their three owning files; no other module queries these tables directly (confirmed
by the full-repo grep in Research Notes finding zero matches outside these three files' real SQL
and the seven test files).

## Test Plan (Adversarial Matrix)

1. **Happy path**: fresh DB (no prior file) — tables are created directly with new prefixed names,
   no rename path triggered. Covered by existing tests once mechanically updated.
2. **Boundary/Edge case**: DB with old-named tables and zero rows — rename succeeds, tables end up
   empty under the new name (not "no rows found so skip rename").
3. **Graceful degradation**: DB with *both* old- and new-named tables present (D-3) — rename is
   skipped for that table, a warning is logged, application still starts and operates against the
   new-named table.
4. **Hostile/real-data**: DB with old-named tables **and real persisted rows** (D-4, D-5) — rename
   preserves every row's data exactly, and FK constraints (`edges.source_id`, `audit_log.run_id`)
   continue to enforce correctly against the renamed tables afterward.

## Phase 5: Consistency Checks (planned, to run post-implementation)

- `python scripts/tests.py cb TECH-005` (with `--kind refactor`, since this is a TECH ticket)
- `tach check` — no boundary changes expected (no new imports, no new modules)
- `python scripts/quality.py cb`
- `python scripts/check_fr_coverage.py TECH-005` — FR-8 must show a citing plan (this file) and a
  citing test (the new migration tests)

---
# Red/Blue Team Review Report

## Summary
- **Target**: TECH-005 SF-3 Implementation Plan
- **Cycles**: 2
- **Findings**: 6 (Cycle 1) + 1 (Cycle 2) = 7
- **Critical/High fixes applied**: 3

## Cycle Log

### 🔴 RED-1.1: Rename-then-crash leaves the DB in a half-migrated state
**Category**: Robustness & Edge Cases
**Severity**: HIGH
**Target**: `_rename_legacy_tables` design in `store.py` (3 tables renamed via 3 separate statements)
**Finding**: If the process is killed (or raises) between renaming `pipeline_runs` and `audit_log`,
the DB is left with `flow_pipeline_runs` + old `audit_log` — a state neither the old nor new code
path expects cleanly, and the next startup's detection logic must handle it.
**Attack Vector**: Power loss / OOM kill mid-migration on a real user's machine.

### 🔵 BLUE-1.1: Response to RED-1.1
**Verdict**: VALID — ACCEPTED, WITH MITIGATION (not full atomicity)
**Response**: All rename statements for a given file run inside the same `with self.connect() as
conn:` block, which for `sqlite3.Connection` used as a context manager commits (or rolls back) as a
single transaction on block exit — so a crash mid-block rolls back to the pre-migration state
entirely (old names, untouched), not a half-migrated one. This is already how `_ensure_schema`'s
existing `executescript` call works, so no new pattern is introduced. Confirmed by reading
`store.py:89-90` (`with self.connect() as conn: conn.executescript(...)`) — same transactional
envelope will wrap the new rename calls. A test (`test_legacy_table_migration_preserves...`)
verifies the end state; an atomicity-under-kill test is out of scope (untestable without actually
killing the process, and the transactional guarantee is a property of `sqlite3`/SQLite itself, not
of code this ticket writes).

### 🔴 RED-1.2: `graph.db`'s per-connection `_init_db()` runs the rename check on every construction
**Category**: Maintainability / Performance
**Severity**: LOW
**Target**: `repository.py:_init_db()` — called from `__init__` every time `SqliteGraphRepository`
is instantiated (once per `sw graph build` invocation, not held open)
**Finding**: The `sqlite_master` lookup for old table names runs on every construction, forever,
even years after every real installation has already migrated.
**Evidence**: `_init_db()` has no version gate at all (unlike `store.py`), so this isn't a
regression — it's the existing `CREATE TABLE IF NOT EXISTS` cost pattern, and a `sqlite_master`
lookup is a single indexed catalog read, not a table scan.

### 🔵 BLUE-1.2: Response to RED-1.2
**Verdict**: INVALID — NO ACTION
**Response**: Cost is one `SELECT name FROM sqlite_master WHERE type='table' AND name IN (...)`
per construction — negligible next to the AST parsing and graph traversal `sw graph build` already
does. Adding a "have I already migrated" cache would be speculative complexity (YAGNI) for a cost
that doesn't show up in any real workflow.

### 🔴 RED-1.3: `graph.db`'s `edges` table has no FK on `target_id` (intentional, lazy edges) — does the rename check need to account for that asymmetry?
**Category**: Correctness
**Severity**: MEDIUM
**Target**: `_rename_legacy_tables` for `repository.py`
**Finding**: Confirm the rename of `edges` doesn't implicitly try to validate `target_id` against
`graph_nodes` and reject rows whose target was a lazy/ghost reference not yet flushed.
**Evidence**: `repository.py:47-55` — `FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE
CASCADE` only; no clause at all for `target_id`.

### 🔵 BLUE-1.3: Response to RED-1.3
**Verdict**: VALID — CONFIRMED SAFE, NO CODE CHANGE NEEDED
**Response**: `ALTER TABLE ... RENAME TO` only rewrites existing FK clauses to point at the new
name — it does not add new constraints. Since `target_id` never had a FK clause, renaming
introduces none. Test Plan item 4 explicitly asserts `source_id`'s FK still enforces post-rename
and does not assert anything about `target_id`, matching this intentional asymmetry.

### 🔴 RED-1.4: `test_migration_v1_to_v2` rename (D-4) changes an existing test's meaning without flagging it as a deliberate reinterpretation
**Category**: Maintainability
**Severity**: MEDIUM
**Target**: D-4
**Finding**: Silently repurposing an existing test's fixture to mean something new (rather than
adding a fresh test) risks looking like scope creep on a pre-existing, working test if the diff
isn't read carefully.
**Evidence**: Same shape as the SF-04 `test_a_path_substitution_plus_an_unrelated_new_line_is_safe`
precedent from this session, where a deliberately changed test outcome needed explicit
justification in its docstring.

### 🔵 BLUE-1.4: Response to RED-1.4
**Verdict**: VALID — FIX REQUIRED
**Response**: The new test docstring will state explicitly why the fixture is reused (the v1
fixture already builds old-named tables, so it's free coverage for the rename) and that this is a
deliberate widening of what the test proves, not an accidental change to its assertions.

### 🔴 RED-1.5: Does `flow_reservations`'s `expires_at` column matter for the rename, given `reservations.db` files may be extremely short-lived (per-run)?
**Category**: Architecture & Design
**Severity**: LOW
**Target**: `reservation.py` scope
**Finding**: Confirm this file's migration path is worth building at all, given `reservations.db`
is created fresh under `<project_path>/.specweaver/` and rows are meant to be transient locks, not
long-lived state.
**Evidence**: `gates.py:109` creates the path per-pipeline-run; `release()` deletes rows by
`run_id` when a run completes.

### 🔵 BLUE-1.5: Response to RED-1.5
**Verdict**: PARTIALLY VALID — BUILD IT ANYWAY, SIMPLER JUSTIFICATION
**Response**: Row *data* being transient doesn't make the *table name* transient — a crashed or
killed pipeline run can leave stale lock rows sitting under the old table name indefinitely (there
is no TTL sweep in `reservation.py` today — `expires_at` is written but never read/enforced,
confirmed by grep: no `expires_at` reference outside the INSERT). Consistency with the other two
files (same rename pattern, same test shape) is worth more than the marginal savings from special-
casing the one file where the risk window happens to usually be short. Built as planned.

### 🔴 RED-1.6: `_rename_legacy_tables` naming collides across three unrelated classes — will a future grep for the term assume it's one shared function?
**Category**: Maintainability
**Severity**: LOW
**Target**: D-1
**Finding**: Three private methods with the identical name `_rename_legacy_tables` (two of them;
`reservation.py` uses the singular `_rename_legacy_table`) living in three different files could
read, out of context, like a shared utility that was supposed to be centralized but wasn't.
**Evidence**: This session's own memory record on grab-bag naming exists specifically because
"shared-sounding" names invite exactly this misreading.

### 🔵 BLUE-1.6: Response to RED-1.6
**Verdict**: VALID — FIX REQUIRED
**Response**: Each method's docstring will name the specific tables it renames (e.g. "Renames
`nodes`→`graph_nodes` and `edges`→`graph_edges` for pre-SF-3 installations") so reading either one
in isolation immediately shows it's scoped to that class's own tables, not a shared abstraction.
The identical method name is fine — it's private, `self`-scoped, and Python has no cross-class
namespace collision here — but the docstring must foreclose the misreading.

## Cycle 2

### 🔴 RED-2.1: Does `_rename_legacy_tables` need to run inside the *same* transaction as the
subsequent `CREATE TABLE IF NOT EXISTS` / version-check logic, or can a second connection interleave?
**Category**: Robustness & Edge Cases
**Severity**: MEDIUM
**Target**: `store.py:_ensure_schema()` ordering
**Finding**: `_ensure_schema()` is called once from `__init__`, but nothing prevents two
`StateStore` instances (e.g. two CLI processes racing at startup) from both reading
`sqlite_master`, both seeing the old name, and both attempting `ALTER TABLE pipeline_runs RENAME TO
flow_pipeline_runs` — the second one would fail with "no such table: pipeline_runs" since the first
already renamed it.
**Evidence**: `gates.py`/`pipelines.py` construct `StateStore`/`SQLiteReservationSystem` per-request
in a FastAPI server context — concurrent construction is a real, not theoretical, scenario.

### 🔵 BLUE-2.1: Response to RED-2.1
**Verdict**: VALID — FIX REQUIRED
**Response**: Guard the rename with the same `IF NOT EXISTS`-style idempotency SQLite gives
`CREATE TABLE` for free, but `ALTER TABLE RENAME` has no such clause — so the rename call must
catch `sqlite3.OperationalError` matching "no such table" and treat it as "another process already
migrated this, nothing to do" rather than letting it propagate. A test drives this by calling the
rename method twice in a row against the same connection (simulating the second racer arriving
after the first already renamed) and asserting the second call is a silent no-op, not a crash.

**No further findings in Cycle 2** below the continuation thresholds (0 CRITICAL, 0 HIGH, 1 MEDIUM
< 5, 0 LOW) — review complete per the skill's stop condition.

## Corrections Made
- D-3's "both exist" handling extended to also cover RED-2.1's "old already gone, new already
  there" race — both are the same code path (attempt rename, tolerate specific already-migrated
  states, never raise for either).
- Added `test_sqlite_reservation_skips_rename_when_both_old_and_new_tables_exist` and an
  analogous double-invocation test to the Test Plan (D-3 + RED-2.1 combined).
- Every `_rename_legacy_table(s)` method's docstring will name its specific tables (RED-1.6).
- `test_migration_v1_to_v2`'s repurposing (D-4) will carry an explicit docstring justification
  (RED-1.4), following the same precedent set in TECH-001 SF-04.

## Accepted Risks
- RED-1.1's true mid-transaction-crash atomicity is not independently tested — it is a property of
  `sqlite3`'s transactional context-manager behavior (already relied upon elsewhere in this
  codebase), not new code this ticket introduces.
- RED-1.2's per-construction `sqlite_master` lookup cost is accepted as negligible; no caching
  added (YAGNI).

*(End of Red/Blue Team Review Report)*
