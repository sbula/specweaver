# Walkthrough: TECH-090 — The Database Is Opened Three Ways

## SF-01 CB-1 — the opener and the step runner (FR-2, FR-3)

**What exists now.** `src/specweaver/infrastructure/database/`, an `adapter` that depends on nothing:
- `open_sqlite`: the wait, then WAL, then foreign keys;
- `create_sqlite_engine`: the same settings through a `connect` event, with `NullPool`;
- `set_lock_wait`: 30 s by default; the door sets it;
- `upgrade`: runs a file's missing steps from `PRAGMA user_version`, each inside `BEGIN IMMEDIATE`
  with a second version read;
- `rename_legacy_tables`: the one rename helper.

Nothing uses it yet; CB-2 moves the first two files.

**Tests.**
- Red first: `test_open_sqlite.py`, `test_steps.py` and `test_two_processes_upgrade.py`. All three
  failed because the module did not exist.
- `test_error_paths.py` added at the gate for three branches the matrix missed.
- Coverage of the package is 100%.
- A step that raises after `ALTER TABLE ADD COLUMN` leaves no column, so the transaction holds DDL.
  This is measured, not assumed.

**Measured and rejected: setting `PRAGMA journal_mode=WAL` once per connection.** The two-process
test failed 8 of 15 runs. On a new file, two processes switching to WAL together get
`database is locked` at once, and `busy_timeout` does not cover the switch. The opener now switches
only when the file is not yet in WAL, and retries until the lock wait ends. After that: 20 of 20.

**Mutants (TECH-090 corpus).**
- FR-2: `foreign-keys-off`, `wal-switch-not-retried`.
- FR-3: `deferred-begin`, `no-second-version-read`, `version-not-recorded`, `newer-file-opened`.
- All objected. The rename guard's mutant also objected; it was run by hand.

**Red/blue (2 cycles).**
- Accepted: a process remembers the files it upgraded. If the file is deleted while a long-lived
  API server runs, the server does not create it again until it restarts.
- Accepted: table names in `rename_legacy_tables` are formatted into SQL. They come only from
  code constants.

Nothing above threshold.

## SF-01 CB-2 — `reservations.db` and `graph.db` on the opener (FR-1, FR-2)

**What changed.** Both stores now open their file through `open_sqlite`. Each keeps its schema as
step 1 of its own step list (AD-3), and the old rename code in each is now the shared helper. The
settings changed as follows:
- `reservations.db` gains foreign keys and a lock wait; before, it had neither.
- `graph.db` waits 30 s instead of 5 s.

**Tests.**
- Red first: `tests/unit/infrastructure/database/test_only_the_opener_opens.py` named both files.
  Its allowlist holds the five openers not moved yet, and a name that stops opening a file must
  leave the list.
- Red first: `test_reservations_on_the_opener.py` and `test_graph_db_on_the_opener.py`. They cover
  the settings, version 1, a file from before versioning, a file with old table names, and a newer
  file being refused.
- Removed: the four unit tests of the two private rename copies; `test_error_paths.py` covers the
  shared helper's same two branches.
- Changed: the reservation schema-error test now breaks a new file, because a file is upgraded once
  per process. The graph lock-wait test now pins 30 s (Q5).

**Mutants.**
- TECH-090 FR-1: `reservations-opened-by-hand` and `graph-schema-unversioned`; both objected.
- TECH-004 FR-4 `no-busy-timeout` now points at the opener's wait line, where the graph store's
  wait lives now; it objected.

**Red/blue.** Nothing above threshold. A step's failure in either store raises `SchemaStepError`
naming the file; the doors' message comes in SF-03.

## SF-01 CB-3 — `pipeline_state.db` on the opener (FR-1, FR-4)

**What changed.**
- `StateStore` opens through `open_sqlite` and keeps its schema as step 1.
- `_adopt_old_version` runs inside step 1's transaction, in this order:
  1. the legacy renames,
  2. read `MAX(version)` from `flow_state_schema_version`,
  3. map it through `_OLD_VERSIONS = {None: 0, 1: 0, 2: 0, 3: 0, 4: 1}`,
  4. set `user_version`,
  5. read it back,
  6. drop the old table.
- `executescript`, which committed before it ran, is gone: step 1 runs its statements one by one.
- The opener's allowlist loses `core/flow/engine/store.py`.

**Found while building:** an old file can hold an empty version table. The old code read that as
"new file" and recorded v4 without checking the columns. The map now names it (`None: 0`), so
step 1 checks everything; a test covers it.

**Tests.**
- Red first: `test_state_version_moves.py`, with test files built as v1 (old table names), v2, v3
  and v4 left them. They cover: each ends at `user_version` 1 with its runs; the empty table; a
  second open in a new process changes nothing; a failure planted before the drop undoes the
  version (measured: `user_version` 0, old table at 4); an unknown version stops.
- Changed: six older store tests read `user_version` instead of the old table.
- Removed: two tests of the private rename copy.

**Mutants.**
- Objected, in the corpus: `drop-before-version`, `old-version-ignored`, `unknown-version-guessed`.
  The last one was silent at first: Python's own `KeyError` also said "7", so the test now requires
  the full message.
- Objected, run by hand (a module constant has no symbol): the map entry 2 → 1.
- **Silent, judged equivalent by the user** `[agreed 2026-11-07]`; the read-back check stays,
  because it guards the order the user asked for:
  - `map 4 → 0`: a v4 file then runs step 1, which changes nothing on today's schema, so the result
    is the same.
  - `no-read-back`: SQLite always reads back a `user_version` set in the same transaction, so the
    check cannot fail.

## SF-02 CB-1 — `Database` on the opener (FR-1)

**What changed.**
- `Database`, `session_scope` and `StrictISODateTime` moved to `infrastructure/database/`, into
  `handle.py` and `types.py`.
- `Database.connect()`, `async_session_scope()` and the new `sync_engine()` all open through the
  opener.
- 157 files' imports were moved by a script that rewrote only those import lines.
  `git diff` shows nothing else, and a grep finds the old path only inside one test's string fixture.
- The lineage repository and price refresh open through the opener too. The lineage repository's
  own WAL-once workaround is gone: the opener retries the switch.
- 11 modules gained the edge. Three of them (`assurance.standards`, its `interfaces`,
  `core.flow.store`) lost their `core.config` edge, which existed only for `Database`.

**Changed from the plan.**
- The plan had `session_scope` and its per-loop semaphore deleted. They moved instead: 48 test files
  use `session_scope`, and the semaphore keeps a burst of sessions from running out of file handles.
- `get_db_semaphore` and the `create_async_engine` wrapper stay in `core/config` until CB-3, with
  their tests.

**Found at the gate.**
- The changed import line made two old clones visible.
  - The copied `Base` classes in the flow, LLM and workspace stores each set `__tablename__` from
    the class name, but every table sets its own name. The rule was dead in all three and is gone.
  - Two API modules share a 10-line import block. It is imports only, so the duplication baseline
    was re-frozen on purpose; it holds 86 clones, down from 89.
- `core/config/bootstrap` now uses the opener while its parent does not; its `widens:` says why.

**Tests.**
- Red first: `test_config_db_on_the_opener.py`, which failed on the import. It covers the three ways
  into `specweaver.db` and the lineage repository: the settings, a missing folder, and the door's
  5 s wait reaching all of them.
- Added at the gate: `test_strict_iso_datetime.py`, for the moved type's two refusals.

**Mutants.**
- TECH-090 FR-1: `config-connect-by-hand`, `config-session-by-hand`, `config-sync-engine-by-hand`,
  `lineage-by-hand`; all objected.
- Re-pinned after the import change: D-UI-01 FR-3 and FR-6 (3), TECH-074 FR-7 (4).

## SF-02 CB-2 — `specweaver.db`'s steps, the schema comparison, Alembic gone (FR-5, FR-6, FR-10)

**What changed.**
- `bootstrap_database` now runs `upgrade(path, _STEPS, adopt=_refuse_pre_prefix_file)` and then
  seeds the prices.
- Step 1 is today's bootstrap:
  - the three metadata sets, compiled to SQL text and run on the step's own connection.
    `create_all` would commit the step's transaction itself;
  - the ten helpers, now on `sqlite3`;
  - `DROP TABLE IF EXISTS alembic_version`.
- A file with the table names from before 2026-07-12 stops before step 1 creates anything (Q1).
- A failed price seed stays a warning (Q2).
- Alembic is gone: `alembic.ini`, `alembic/`, its test, the dependency and `uv.lock` (the user ran
  `uv lock`). `docs/architecture/03_system_topology/database_migrations.md` now describes the
  steps.

**Found while building.**
- The first version of step 1 added indexes to tables that already existed. On an older
  `llm_usage_log` that names a column a later helper adds. `create_all` creates indexes only with
  the tables it creates, and step 1 now does the same; an old test caught it.
- The bootstrap printing its schema to stdout (TECH-054 FR-2) was proven only by tests that never
  start from a new file. Step 1 now runs once per file, so `test_a_new_file_prints_nothing_to_stdout`
  was added and the mutant objects again.

**TECH-005, decided by the user 2026-11-07.**
- FR-1, FR-2 and FR-6 were cited only by the deleted Alembic test. They now have a real one,
  `test_config_tables_carry_their_context.py`, which killed both mutants (a model back to its old
  table name).
- FR-3 (a table `C-FLOW-13` already retired) and FR-7 (the Alembic migration) were removed from
  TECH-005's FR table, with a note saying why.

**Tests.**
- Red first: `test_config_db_steps.py` and `test_no_alembic.py`.
- `test_schema_is_one_schema.py` was green from the start, as expected: both files come from the
  same code until the change, and it must stay green after it. Its own red cases objected.
- The old state is `tests/fixtures/specweaver_db_before_tech_090.sql`, frozen from the bootstrap at
  `58632d7a` before the code changed.
- Five tests that turned an upgraded file back into an older one in the same process now use
  `as_a_new_process()` and set `user_version` 0, as a later `sw` start would see it. Two
  invalid-path tests now expect `sqlite3.OperationalError`.

**Mutants.**
- TECH-090 FR-5: `alembic-version-kept`, `call-status-not-added`, `console-level-not-added`,
  `pre-prefix-file-accepted`, `indexes-on-old-tables`; all objected.
- By hand: the seed warning turned into a raise; `reached_at` not added. Both objected.
- Re-anchored on the new lines: B-FLOW-07, C-FLOW-01, C-FLOW-13, D-FLOW-04, TECH-054 and TECH-074
  (four).

**Red/blue.** Nothing above threshold. Accepted: like `create_all` before, step 1 never adds an
index to a table that already exists; a later index on an existing table needs its own step.

## SF-02 CB-3 — `core/config` is pure logic again (FR-11)

**What changed.**
- `core/config/database.py` is deleted: the write queue nothing used, the second foreign-key
  listener, and the re-exports of the opener.
- `PipelineRunner.run` and `.resume` no longer open the empty queue.
- The private `_now_iso` copies are gone: the flow store uses `commons.timestamps.now_iso`, and the
  dead copy in `workspace/store.py` was removed. The re-export in `workspace/memory/store.py` went too.
- `core.flow.engine` and `workspace.memory` lost their `core.config` edge (tach and `context.yaml`).
- `test_only_the_opener_opens.py` has an empty allowlist: no file opens SQLite outside the opener.
- Test engines: `tests/fixtures/db_utils.create_async_engine` (NullPool, foreign keys on), used by
  15 test files.

**Docs.** `domain_driven_cli_creation.md`, `special_patterns_and_adaptations.md` §21,
`testing_guide.md`, `core/CLAUDE.md`, and `cqrs_and_database.md` (rewritten: the one opener, no
queue). `test_cqrs_e2e.py` keeps its name, which other documents cite; its stale queue words are gone.

**Coverage.**

| Unit under change | Unit | Integration | E2E |
|---|---|---|---|
| `core/config` has no I/O, no `_now_iso` copy | ✅ `test_config_is_pure_logic.py` | — | — |
| `session_scope` commit, rollback, cap, per-loop semaphore | ✅ `test_session_scope.py` | ✅ `test_sessions_integration.py` | — |
| a product session has foreign keys on | ✅ `test_session_scope.py` | ✅ memory tests | ✅ `test_runs_keep_memory_e2e.py` |
| runner without the queue | ✅ `test_engine_runner.py` | ✅ flow engine | ✅ `test_cqrs_e2e.py` |

**Found at the gate.**
- `test_an_error_inside_the_scope_rolls_back` was false. It made a table inside the scope, and the
  driver does not open a transaction for `CREATE TABLE`, so the table stayed. It now inserts a row,
  fails, and expects the row gone. A mutant (rollback turned into commit) objects.
- Eight B-INTL-09 campaigns named the deleted `test_database.py`; they now name
  `test_session_scope.py`.

**B-INTL-09 FR-6** said every session enforces foreign keys and runs Alembic. The Alembic half no
longer applies: TECH-090 removed Alembic. The foreign-key half is now proven by
`test_a_product_session_has_foreign_keys_on`. B-INTL-09 itself was not edited; only its mutant
`fk-off` was moved to `apply_pragmas`.

**Tests.** `tests.py sf TECH-090 --kind bugfix`: unit 10101 passed (9 skipped), integration 2235,
e2e 84. `quality.py sf`: 18 of 18. `quality.py doc`: 14 of 14. `tach check` green.

**Mutants.**
- By hand (a module-level import cannot be a corpus symbol): `import sqlite3` in `paths.py`; a late
  `sqlalchemy` import inside `specweaver_root`; a `_now_iso` function back in the flow store.
  All objected.
- `session_scope` rollback turned into a commit: objected.
- Re-pinned after the runner change: D-UI-01 FR-4, B-FLOW-05 FR-8. Re-anchored: B-INTL-09 FR-6
  `fk-off`. Stale mutants: 0.

**Red/blue** (2 cycles, nothing above threshold). Accepted:
- `handlers/base._now_iso` stays: it is an alias of `commons.now_iso`, not a copy. Its 20 importers
  are out of this ticket.
- The test engine turns foreign keys on with its own listener. The product path has its own test,
  so a drift between them is caught.
- The I/O guard reads only `core/config/*.py`. `core/config/bootstrap/` does I/O on purpose and
  declares it in its own `context.yaml`.

## SF-03 CB-1 — the CLI door (FR-7, FR-8)

**What changed.**
- `steps.py`: one error family. `SchemaError` is the base of `SchemaTooNewError`,
  `SchemaStepError` and the new `SchemaOpenError`. `upgrade` turns a file it cannot open (not a
  database, a folder, locked past the wait) into `<path> cannot be opened: <cause>`.
- `db_bootstrap.get_db` raises; it no longer warns and goes on.
- `cli_kit/_core`: `stops_on_schema_error()` prints a `SchemaError` and exits 1, and catches
  nothing else. `get_db` opens under it; its first use in a command switches logging to the
  active project at its levels.
- The CLI callback opens no database: it resets that switch, sets the 30 s lock wait and logging at
  the defaults. `sw run --help` works on a broken database and creates none.
- `_get_state_store` (`sw run`, `sw resume`) opens under the same catch.
- `cli_kit` gains the `infrastructure.database` and `telemetry_logger` edges.

**Docs.** `1_installation_and_setup.md` §8: a command logs to `_global` until its first database use.

**Coverage.**

| Unit under change | Unit | Integration | E2E |
|---|---|---|---|
| `SchemaOpenError`, one family | ✅ `test_steps.py` | ✅ `test_cli_stops_on_a_failed_step.py` | — |
| `stops_on_schema_error` | ✅ `test_stops_on_schema_error.py` | ✅ `test_cli_stops_on_a_failed_step.py` | — |
| callback: no database, 30 s, defaults | ✅ `test_help_opens_no_database.py`, `test_cli_door_settings.py` | — | ✅ `test_fresh_machine_cli_e2e.py` |
| project log at first use, reset per command | ✅ `test_cli_door_settings.py` | — | ✅ `test_cli_logging_e2e.py` |
| `sw run`, `sw resume`, `sw graph build` on a newer file | — | ✅ `test_cli_stops_on_a_failed_step.py` | — |

**Found at the gate.**
- A command logs its first line ("Executing projects command") before its first database use, so
  that line now goes to `_global`, not to the project's file. This follows from the Q2 decision.
  `test_cli_logging_e2e.py` now checks the switch's own record in the project's file. For the
  user to review.
- `sw run` on a newer `pipeline_state.db` already stopped with the message before this boundary;
  `sw resume` gave a traceback. `sw graph build` already printed the file; its test guards that.
- The wrap around the first `user_version` read was dead: opening already reads the file. Removed.
- Two folder-as-file tests expected `sqlite3.OperationalError`; they now expect `SchemaOpenError`.

**Tests.** Full suite: 12807 passed, 9 skipped. `quality.py cb`: 17 of 17. `quality.py doc`: 14 of
14. `tach check` green.

**Mutants.** FR-7: 6, FR-8: 4, all objected; the catch widened to `Exception` objects too.
Re-pinned after the change: TECH-081 FR-16, TECH-090 FR-3. Stale mutants: 0.

**Red/blue** (2 cycles, nothing above threshold). Fixed: a redundant `except (ValueError,
Exception)`. Accepted:
- The switch flag is module state; a command function called without the callback keeps the last
  value. Only tests do that, and `tests/conftest.py` restores the logger.
- If reading the active project fails, the command stops with that error, as it did in the
  callback before.
