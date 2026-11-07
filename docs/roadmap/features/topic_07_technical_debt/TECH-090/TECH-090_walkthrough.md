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
