# Implementation Plan: The Database Is Opened Three Ways [SF-01: One opener, versioned steps]
- **Feature ID**: TECH-090
- **Sub-Feature**: SF-01 — One opener, versioned steps
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_sf01_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-07)

## Scope

FR-1 for `pipeline_state.db`, `graph.db` and `reservations.db`; FR-2; FR-3; FR-4. The package
`infrastructure/database/` with a sync opener, an async engine factory (used by SF-02), the step
runner and one legacy-rename helper. `specweaver.db` stays on its old openers until SF-02.

## The package

| Module | Holds |
|---|---|
| `infrastructure/database/sqlite.py` | `open_sqlite(path, *, row_factory=None, isolation_level="") -> sqlite3.Connection`; `set_lock_wait(seconds)`, `lock_wait_seconds()` |
| `infrastructure/database/engine.py` | `create_sqlite_engine(path) -> AsyncEngine`: the same pragmas through a `connect` event, `NullPool` |
| `infrastructure/database/steps.py` | `Step(version, name, apply)`; `upgrade(path, steps, *, adopt=None)`; `SchemaTooNewError`, `SchemaStepError` |
| `infrastructure/database/legacy.py` | `rename_legacy_tables(conn, renames)`: the one copy of today's three rename helpers |

`open_sqlite`, in order: connect with `timeout=lock_wait_seconds()`; `PRAGMA busy_timeout` (first,
so the WAL switch below waits for a lock instead of failing at once); `PRAGMA journal_mode=WAL`
(outside any transaction: SQLite refuses it inside one); `PRAGMA foreign_keys=ON` (a no-op inside a
transaction). The lock wait defaults to 30 s; SF-03's API door sets 5 s
(design AD-5).

`upgrade`, in order:
0. a path this process has already upgraded returns at once (a per-process set): stores are built
   many times per run, and FR-3 says the steps run the first time a process opens the file;
1. open with `isolation_level=None`, so Python's `sqlite3` adds no `BEGIN` of its own (3.11 has
   no `autocommit=`);
2. read `user_version`; above the highest step → `SchemaTooNewError(path, found, known)`;
3. for each missing step: `BEGIN IMMEDIATE`; read `user_version` again (another process may have
   applied it while this one waited); if still missing: on the first step only, `adopt(conn)`;
   then `apply(conn)`; `PRAGMA user_version = step.version`; `COMMIT`;
4. on any error: `ROLLBACK`, then `SchemaStepError(path, step.name, cause)`.

No step may use `executescript`: it commits before it runs.

## The three files

| File | Owner (keeps its step list, AD-3) | Step 1 | Old state |
|---|---|---|---|
| `reservations.db` | `core/flow/engine/reservation.py` | rename `sw_reservations`; `CREATE TABLE IF NOT EXISTS flow_reservations` | none; `user_version` 0 runs step 1 safely |
| `graph.db` | `graph/core/store/repository.py` | rename `nodes`, `edges`; today's two `CREATE TABLE IF NOT EXISTS` | none |
| `pipeline_state.db` | `core/flow/engine/store.py` | renames; the tables of today's schema v4, as single statements; `parent_run_id` and `spend_state` added where missing | `flow_state_schema_version` v1..v4 (FR-4) |

FR-4's map, in `store.py`, beside the step list:

| Old `flow_state_schema_version` | Means | `user_version` set by `adopt` |
|---|---|---|
| 1 | no `parent_run_id`, no `spend_state` | 0: step 1 adds both |
| 2, 3 | no `spend_state` | 0: step 1 adds it |
| 4 | today's schema | 1 |
| none (new file) | — | not called |

`adopt`, inside step 1's transaction, after the legacy renames (a v1 file still calls the table
`state_schema_version`): read `MAX(version)`; look it up (a value not in the map is a
`SchemaStepError`, not a guess); set `user_version`; read it back and compare; `DROP TABLE
flow_state_schema_version`. If the map says 1, step 1 does not run.

## Commit boundaries

### CB-1 (interior): the opener and the runner — FR-2, FR-3
- **Red first**: `tests/unit/infrastructure/database/test_open_sqlite.py` (no module yet):
  - pragmas read back as WAL, `foreign_keys` 1, `busy_timeout` 30000 on a new file and on an
    existing one; `set_lock_wait(5)` gives 5000;
  - the async engine's connection reads back the same three.
- **Red first**: `tests/unit/infrastructure/database/test_steps.py`:
  - only missing steps run;
  - a second run changes nothing;
  - a file at a version above the steps → `SchemaTooNewError` naming the file and both versions;
  - a step that raises after an `ALTER TABLE ADD COLUMN` leaves no column and the old version
    (the transaction holds DDL: measured, not assumed);
  - `rename_legacy_tables` handles the race: the rename is lost to another process and the new
    table exists, so no error.
- **Integration**: `tests/integration/infrastructure/database/test_two_processes_upgrade.py`: two
  processes, started together behind a barrier, upgrade one file; each step's side effect happens
  once; both end at the same version.
- **Mutants**: drop `BEGIN IMMEDIATE`; drop the second version read; drop the `SchemaTooNewError`
  check; drop `foreign_keys=ON`.
- The guide section "how to add a schema step" in `docs/dev_guides/working_in_this_repo.md`.
- `tach.toml`: module `specweaver.infrastructure.database`, `depends_on = []`;
  `infrastructure/database/context.yaml`: `archetype: adapter`, `consumes: []`.

### CB-2 (interior): `reservations.db` and `graph.db` — FR-1 (two files), FR-2
- **Red first**: `tests/unit/infrastructure/database/test_only_the_opener_opens.py`: no
  `sqlite3.connect`, `create_engine` or `create_async_engine` in `src` outside
  `infrastructure/database/`, except a named allowlist that SF-02 empties:
  `core/config/database.py`, `core/config/bootstrap/db_bootstrap.py`,
  `infrastructure/llm/price_refresh.py`, `graph/lineage/store/lineage_repository.py`, and
  `core/flow/engine/store.py` until CB-3. A planted call is caught.
- Integration: both stores' files read back the pragmas (FR-2: today `reservations.db` has no
  foreign keys and no busy wait; `graph.db` waits 5 s); an old file with the old table names keeps
  its rows; a file at `user_version` 0 with today's tables runs step 1 and keeps its rows.
- `tach.toml` and `context.yaml`: `core.flow.engine` and `graph` gain
  `infrastructure.database`.

### CB-3 (closes SF-01, HITL): `pipeline_state.db` — FR-1 (third file), FR-4
- **Red first**: `tests/integration/core/flow/engine/test_state_version_moves.py`, with test files
  built at v1, v2, v3 and v4 (old table names for v1, as old installs had), each holding runs:
  - each ends at the mapped `user_version`, with all its runs, and no `flow_state_schema_version`;
  - a second open changes nothing;
  - a failure planted after `user_version` is set and before the `DROP` leaves the old table and
    `user_version` 0 (the rollback is measured);
  - a version not in the map stops naming it.
- The allowlist loses `core/flow/engine/store.py`.
- **Mutants**: the map entry 4 → 0; drop the read-back; move the `DROP` before the read-back.

## Research Notes

- `StateStore.connect()` (`core/flow/engine/store.py:117`) is used at 10 call sites and sets
  `row_factory = sqlite3.Row`: `open_sqlite`'s `row_factory` keeps them unchanged.
- `StateStore._ensure_schema` (:161) uses `executescript(_STATE_SCHEMA_V2)`, which commits first:
  step 1 runs the same statements one by one.
- `SQLiteReservationSystem._get_connection` (`reservation.py:23`) uses
  `isolation_level="IMMEDIATE"` for `acquire`: kept for its normal connections.
- `SqliteGraphRepository._get_connection` (`graph/core/store/repository.py:41`): 5 s wait today.
- `graph/context.yaml` forbids `core/config`; the opener depends on nothing, so the edge is legal.
- Python `sqlite3`: `executescript` commits first; DDL in legacy mode runs outside a transaction
  unless `BEGIN` is issued (docs.python.org/3/library/sqlite3.html).

## Red/Blue (Phase 5), 2 cycles

Cycle 1: (HIGH) the WAL switch could fail at once under a lock: `busy_timeout` now comes first.
(MEDIUM) stores are built many times per run: a per-process set skips files already upgraded.
(MEDIUM) `reservations.db` needs `IMMEDIATE`: `open_sqlite` takes `isolation_level`. (MEDIUM) a v1
file has the old table name: `adopt` runs after the renames. Cycle 2: none above threshold.

## Decisions (Phase 4, the user, 2026-11-07: "A, go on")

- Old `pipeline_state.db` versions map as the table above: v1..v3 → 0, v4 → 1 `[agreed 2026-11-07]`.
- The lock wait is a module setting, default 30 s, set once by the door; a test fixture resets it
  `[agreed 2026-11-07]`.
- Connections outside the step runner keep today's transaction mode; only the runner uses
  `isolation_level=None` `[agreed 2026-11-07]`.
- The two-process test uses real processes with a barrier, in the integration tier
  `[agreed 2026-11-07]`.
- `graph.db` moves now; if `TECH-088` retires it, its step list goes with it `[agreed 2026-11-07]`.
- "How to add a schema step" goes into `docs/dev_guides/working_in_this_repo.md` in CB-1
  `[agreed 2026-11-07]`.
