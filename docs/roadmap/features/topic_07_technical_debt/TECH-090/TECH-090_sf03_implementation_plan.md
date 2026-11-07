# Implementation Plan: The Database Is Opened Three Ways [SF-03: The doors]
- **Feature ID**: TECH-090
- **Sub-Feature**: SF-03 — The doors
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_sf03_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-7, FR-8, FR-9, FR-12. After SF-03, the CLI and the API bring each file up to date before the
first work that uses it, a failed step stops them with a message, help opens no database, and a
locked file answers `503`. Paths P-1, P-2, P-4 and P-5 are walked.

## Where things go

| Door | Today | After SF-03 |
|---|---|---|
| CLI callback (`interfaces/cli/main.py:_app_callback`) | reads the active project and its log levels through the database before every subcommand, `sw run --help` included | sets the lock wait (30 s) and logging at the defaults; opens no database (FR-8, AD-4, AD-5) |
| CLI `get_db()` (`core/config/bootstrap/db_bootstrap.py`) | a failed bootstrap is a warning; the command goes on | raises; `cli_kit/_core.get_db` prints the error and exits 1 (FR-7) |
| CLI project logging | in the callback | the first `cli_kit` database use reads the active project and switches logging to it (AD-4) |
| `sw run`, `sw resume` state store (`core/flow/interfaces/cli.py:_get_state_store`) | a failed step is a traceback | the same message and exit 1 (FR-7) |
| `sw graph build` (`graph/interfaces/cli.py:build`) | `SqliteGraphRepository` is made first in `build_target`; any error prints `Failed to build graph` and exits 1 | unchanged in code; a test proves a failed step stops it, naming the file and the step (FR-7) |
| run setup (`interfaces/run_setup/builder.py:build_run`) | `reservations.db` first opened at a `RESERVE` gate, after a step ran | `build_run` brings `reservations.db` up to date first, creating it if missing (FR-7, Q13) |
| `sw serve` (`interfaces/cli/routers/serve_router.py`) | `Database(config_db_path())`, no bootstrap | `_core.get_db()`, so a failure exits with the message before the server starts |
| `create_app()` (`interfaces/api/app.py`) | `Database(config_db_path())`, no bootstrap, no logging, the CLI's 30 s wait | sets the lock wait to 5 s, sets up logging (FR-12), runs `bootstrap_database` on its database and the pipeline state's steps; a failure raises and the app is not built (FR-7) |
| API errors (`interfaces/api/errors.py`) | a locked file is a `500` with the SQL error | `503`, `Retry-After: 1`, no SQL in the body; every other database error stays `500` (FR-9) |

One error family: `SchemaTooNewError` and `SchemaStepError` get a common base `SchemaError` in
`infrastructure/database/steps.py`, exported. A door catches `SchemaError`, nothing wider: a pre-`TECH-005`
file already arrives as a `SchemaStepError`, because its refusal runs inside step 1.

A third member, `SchemaOpenError(path, cause)`: `upgrade` wraps its `open_sqlite` and its first
`user_version` read, so a file that is not a database (`sqlite3.DatabaseError: file is not a
database`) or stays locked past the wait stops with `<path> cannot be opened: <cause>`, not a
traceback. The steps themselves keep `SchemaStepError`.

One catch for the CLI: `cli_kit/_core.stops_on_schema_error()`, a context manager that prints the
`SchemaError` (`print_error`) and raises `typer.Exit(1)`. `get_db`, `_get_state_store` and
`run_doors.build_run_or_exit` all use it, so only `cli_kit` gains the `infrastructure.database` edge.

## Commit boundaries

### CB-1 (interior): the CLI door — FR-7 (CLI), FR-8

**Tests first, each red before the code:**
- `tests/unit/interfaces/cli/test_help_opens_no_database.py`: with `SPECWEAVER_DATA_DIR` holding a
  `specweaver.db` that is not a database (garbage bytes), `sw --help`, `sw --version`,
  `sw run --help`, `sw graph build --help` show their text and exit 0; with an empty data dir no
  `specweaver.db` is created. Red today: the callback reads the database.
- `tests/integration/interfaces/cli/test_cli_stops_on_a_failed_step.py`:
  - a `specweaver.db` at `user_version` 99 → `sw projects` prints the file and both versions, exit
    1, no traceback;
  - a file with the pre-`TECH-005` table names → the message names the file and step 1;
  - a `specweaver.db` of garbage bytes → `sw projects` prints `cannot be opened` and the file, exit
    1, no traceback;
  - a `pipeline_state.db` at `user_version` 99 → `sw run` stops with its message before any step;
  - a `graph.db` at `user_version` 99 → `sw graph build` names the file;
  - after a successful command the file is at the current version.
  Red today: `get_db` warns and the command goes on.
- `tests/unit/interfaces/cli/test_cli_door_settings.py`: after the callback, `lock_wait_seconds()`
  is 30; a command that uses the database logs to the active project's file at the project's
  levels; a command that needs no database logs at the defaults (AD-4); two `CliRunner`
  invocations in one process with different active projects each log to their own project's file
  (the switch flag is reset per invocation).
- e2e `tests/e2e/capabilities/interfaces/test_fresh_machine_cli_e2e.py` (P-1, P-5): a fresh data dir;
  `sw run --help` leaves it without a database; `sw init` makes `specweaver.db` at the current
  version. Written before the callback change; its first half is red.

**Then the code:**
1. `SchemaError` base and `SchemaOpenError` in `steps.py`; export both. Unit tests in
   `tests/unit/infrastructure/database/` for the garbage-file case.
2. `db_bootstrap.get_db()` raises (no `try`).
3. `cli_kit/_core.stops_on_schema_error()` (above).
4. `cli_kit/_core.get_db()` is a function defined in `_core` (not the re-exported name), so
   `graph/interfaces/cli.py`'s `from … _core import get_db` gets it too. Order:
   - open under `stops_on_schema_error()`;
   - if the switch flag is unset: set it **first**, so the reads below, which go through
     `run_repo_op` → `get_db`, do not recurse;
   - read the active project and its two levels as the callback does today (a bad level falls
     back to the defaults, logged at debug); call `setup_logging(project, level, console_level)`.
5. `_app_callback`: reset the switch flag, `set_lock_wait(30)`, `setup_logging()` at the defaults,
   no database.
6. `_get_state_store()`: under `stops_on_schema_error()`.
7. `cli_kit` gains the `infrastructure.database` edge (tach, `context.yaml`).

**Mutants (expected to object):** the callback reading the active project again; `get_db`
swallowing the error again; the `cli_kit` catch removed; `set_lock_wait(30)` removed; the project
logging switch removed; the flag reset in the callback removed; `SchemaOpenError`'s wrap removed.

### CB-2 (interior): `reservations.db` in the run setup — FR-7

**Tests first:**
- `tests/integration/interfaces/run_setup/test_run_setup_prepares_reservations.py`: `build_run` on a
  project without `.specweaver/reservations.db` creates it at the current version before returning;
  a `reservations.db` at `user_version` 99 makes `build_run` raise `SchemaError`, and no run starts;
  through the CLI (`sw run`) the same file stops the command with its message. Red today: nothing
  opens it before the gate.

**Then the code:** `build_run` calls a small `prepare_reservations(project_root)` beside
`SQLiteReservationSystem` in `core/flow/engine/reservation.py`, which runs the file's steps.
`run_doors.build_run_or_exit` calls `build_run` under `_core.stops_on_schema_error()`; no new edge.
An API route that builds a run gets today's `500` on a `SchemaError`.

**Mutants:** the `prepare_reservations` call removed; the CLI catch removed.

### CB-3 (closes SF-03, HITL): the API door — FR-7 (API), FR-9, FR-12

**Tests first:**
- `tests/integration/interfaces/api/test_api_door_prepares_files.py`: `create_app()` on a fresh data
  dir leaves `specweaver.db` and `pipeline_state.db` at their current versions; `create_app(db=…)`
  brings that database's file up to date; a `specweaver.db` at `user_version` 99 makes `create_app`
  raise `SchemaError`; `sw serve` with the same file exits 1 with the message and starts no server;
  after `create_app`, `lock_wait_seconds()` is 5.
- `tests/integration/interfaces/api/test_api_busy_database.py` (P-4): a second connection holds
  `BEGIN IMMEDIATE` on the config database; `POST /api/v1/projects/{name}/use` answers `503` with
  `Retry-After: 1` and no SQL text in the body. The test lowers the wait to keep the suite fast, and
  states that; the 5 s value is proven by the test above. A `500` stays a `500`: a route made to
  raise another `OperationalError` gets `500`.
- `tests/integration/interfaces/api/test_api_logging.py`: after `create_app`, a log record from a
  route reaches `logs/_api/specweaver.log` under the data dir, and not `logs/_global/` (Q1).
- e2e `tests/e2e/capabilities/interfaces/test_fresh_machine_api_e2e.py` (P-2): a fresh data dir,
  `create_app(token=…)` → `/healthz` 200 and `GET /api/v1/projects` 200 (with the token) on a
  current schema.

**Then the code:**
1. `Database` gains a read-only `path` property (today only `_db_path`).
2. `create_app`, in this order: `set_lock_wait(5)`; `setup_logging(project_name="_api")` (Q1);
   `bootstrap_database(str(db.path))` for the given or default database; `StateStore(state_db_path())`,
   whose constructor runs the pipeline state's steps; then the app. Any `SchemaError` propagates.
   `_api` can never be a project's name: project names match `^[a-z0-9][a-z0-9_-]*$`
   (`workspace/store.py:25`).
3. `errors.py`: a handler for `sqlalchemy.exc.OperationalError` and `sqlite3.OperationalError`;
   "locked" or "busy" in the driver message → `503`, header `Retry-After: 1`, body
   `{"detail": "The database is busy. Retry.", "error_code": "DATABASE_BUSY"}` (Q3); anything else
   is re-raised, so it stays today's `500`.
4. `serve_router.serve`: `_core.get_db()` instead of `Database(config_db_path())`. The callback sets
   30 s, then `create_app` sets 5 s: the server runs with 5 s.

**Mutants:** `set_lock_wait(5)` removed; the bootstrap in `create_app` removed; the state steps
removed; the `503` turned into `500`; `Retry-After` removed; the logging call removed.

## Research Notes

- `Click` runs a group's callback before the subcommand parses `--help`
  (`MultiCommand.invoke`), so only an empty callback keeps `sw run --help` away from the database.
  `sw --help` and `sw --version` exit before the callback today.
- `upgrade` remembers each file per process (`_UPGRADED`), so calling `get_db()` many times costs
  one `upgrade` per file and process. `create_app(db=...)` in tests reuses an upgraded file at no cost.
- `setup_logging` swaps all handlers when the project name changes, and is idempotent for the
  same name (`telemetry_logger.py:133-146`). So "defaults first, the project later" works without
  duplicated handlers.
- `tests/conftest.py:173` restores the lock wait after each test, and `:194` restores the logger's
  project tag; `create_app` in a test leaks neither.
- Under WAL a read does not wait for a writer, so only a write route can prove FR-9:
  `POST /projects/{name}/use` writes the active project (`v1/projects.py:151`).
- `sw run` opens the state store at `cli.py:346`, after `build_run_or_exit` and before the runner
  starts; `sw resume` at `:462`.
- No bundled pipeline uses a `RESERVE` gate; `sandboxed_execution.py:144` opens
  `reservations.db` to release a lock after every sandboxed run, which also creates it.
- `graph/interfaces/cli.py:build` already catches every error and exits 1; the graph repository is
  the first thing `GraphOrchestrator.build_target` makes, before any file is read.

## Architecture (Phase 3)

- New edges: `interfaces.cli_kit` → `infrastructure.database` (`SchemaError`); `interfaces.api` →
  `telemetry_logger` (FR-12). Both are door → adapter, downward; `tach.toml` and `context.yaml`.
  `core.flow.interfaces` and `interfaces.run_doors` catch through `cli_kit`, which both already
  depend on, so they gain no edge. `interfaces.api` already depends on `infrastructure.database`.
- `interfaces.run_setup` → `core.flow.engine` exists already; `run_setup` raises and never exits,
  so the catch for `reservations.db` sits in `run_doors`, and the API route returns its `500`.
- No cycle: `infrastructure.database` still depends on nothing.

## Decisions (Phase 4)

- **Q1** The API logs to `~/.specweaver/logs/_api/specweaver.log`, its own file in the CLI's log
  folder, so the CLI and the server never rotate one file `[agreed 2026-11-07]`.
- **Q2** A CLI command switches to its project's log file at its first database use
  (`cli_kit.get_db`) `[agreed 2026-11-07]`.
- **Q3** The `503` body is `{"detail": "The database is busy. Retry.", "error_code":
  "DATABASE_BUSY"}` `[agreed 2026-11-07]`.
