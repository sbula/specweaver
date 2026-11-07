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
