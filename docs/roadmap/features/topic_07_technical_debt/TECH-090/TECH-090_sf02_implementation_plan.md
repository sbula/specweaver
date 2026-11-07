# Implementation Plan: The Database Is Opened Three Ways [SF-02: The config database on the opener]
- **Feature ID**: TECH-090
- **Sub-Feature**: SF-02 — The config database on the opener
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_sf02_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-07)

## Scope

FR-1 for `specweaver.db`, FR-5, FR-6, FR-10, FR-11. After SF-02, the one-opener guard's allowlist is
empty and `core/config` holds no engine, queue, file handler or SQLAlchemy type.

## Where things go

| Today (`core/config/database.py`) | After SF-02 | Why |
|---|---|---|
| `Database` (`connect`, `async_session_scope`) | `infrastructure/database/handle.py` `Database`, on `open_sqlite` and `create_sqlite_engine` | the one opener (FR-1) |
| `StrictISODateTime` (a column type) | `infrastructure/database/types.py` | an SQLAlchemy type is a framework import; `core/config` is `pure-logic` |
| `register_fk_pragma_listener`, `create_async_engine` wrapper, `session_scope`, `get_db_semaphore` | gone: `create_sqlite_engine` sets the pragmas | FR-2 already covers them |
| `CQRSQueueManager`, `get_global_write_queue`, `cqrs_context`, the dead-letter log | gone; `core/flow/engine/runner.py:195,252` lose their `async with cqrs_context()` | nothing ever wrote to the queue (FR-11) |
| `_PROJECT_NAME_RE`, `_now_iso`, `_validate_project_name` | gone | no caller (FR-11) |
| `infrastructure/llm/price_refresh.py` `create_engine("sqlite://", creator=db.connect)` | `Database.sync_engine()` in the handle | the guard allows no `create_engine` outside the opener |
| `graph/lineage/store/lineage_repository.py` `sqlite3.connect` | `open_sqlite` | FR-1; it opens `specweaver.db` |
| `bootstrap_database` (`core/config/bootstrap/db_bootstrap.py`) | the same module keeps `specweaver.db`'s step list (AD-3); `bootstrap_database(path)` runs `upgrade(path, _STEPS, adopt=...)`, then seeds prices | the bootstrap package is an `adapter` and already consumes the models' modules |

The 4 `_now_iso` copies (`core/flow/engine/store.py:474` after SF-01, `workspace/store.py:24`,
`graph/lineage/store/lineage_repository.py:12`, `core/config/database.py:251`) give way to
`commons.timestamps.now_iso` (FR-11).

## Step 1 of `specweaver.db`

Step 1 is today's `bootstrap_database`, unchanged in effect:
1. `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` for the three metadata sets
   (`WorkspaceBase`, `LlmBase`, `FlowBase`, memory models included), compiled to SQL text by
   SQLAlchemy and run on the step's own `sqlite3` connection;
2. today's ten helpers, rewritten from `Connection.exec_driver_sql` to `sqlite3.Connection.execute`,
   each still idempotent;
3. `DROP TABLE IF EXISTS alembic_version` (FR-5).

> [!CAUTION]
> `metadata.create_all` cannot run inside the step: SQLAlchemy commits its own transaction, and the
> step runner's `BEGIN IMMEDIATE` would be committed early. So the DDL is compiled and run as text.

`_move_default_dal_once` keeps its `specweaver_migrations` marker: the marker is what makes it
idempotent on a file at version 0.

Seeding prices is data, not schema; it runs after `upgrade`, as today (Q2).

## Commit boundaries

### CB-1 (interior): `Database` on the opener — FR-1
- **Red first**: `tests/integration/infrastructure/database/test_config_db_on_the_opener.py`:
  - `Database(path).connect()` and a session from `async_session_scope()` both read back WAL,
    foreign keys and the lock wait;
  - the lineage repository's connection does too;
  - price refresh runs through `Database.sync_engine()`.
- Green: the handle and the type move; every `from specweaver.core.config.database import
  Database|StrictISODateTime` import changes (about 21 source and 132 test files). The change is
  made by a script that rewrites only those import lines, then checked with `git diff --stat`, the
  suite and a grep for the old path.
- The allowlist loses `infrastructure/llm/price_refresh.py` and
  `graph/lineage/store/lineage_repository.py`.
- **Mutants**: `Database.connect` back to `sqlite3.connect`; the session engine without the
  `connect` event.

### CB-2 (interior): the steps, the schema comparison, Alembic — FR-5, FR-6, FR-10
- **Red first**: `tests/integration/core/config/bootstrap/test_config_db_steps.py`:
  - a new file ends at `user_version` 1;
  - a file the release before this ticket made (today's `bootstrap_database`, `user_version` 0) ends
    at 1 with every row;
  - a leftover `alembic_version` is dropped;
  - a file with the old table names stops naming the file and the date, and is left unchanged;
  - a failure planted in step 1 leaves the file at 0, and `bootstrap_database` raises (the doors'
    stop is SF-03).
- **Red first**: `tests/integration/core/config/bootstrap/test_schema_is_one_schema.py` (FR-6): the
  schema of a new file and of each upgraded old state compared table by table (columns, types,
  NOT NULL, defaults, indexes). The one listed difference is the four defaults
  `[agreed 2026-11-07]`; Q1 decides the old states.
- **Red first**: `tests/unit/test_no_alembic.py`: no `alembic.ini`, no `alembic/`, no `alembic`
  in `pyproject.toml` or an import.
- Green: step 1; `alembic.ini`, `alembic/`, `tests/unit/alembic/` deleted; `alembic` out of
  `pyproject.toml` and `uv.lock` (`uv lock`); `tests/unit/test_macro_domain_layout.py` and
  `tests/unit/scripts/test_check_conventions.py` lose their `alembic` entries.
- The allowlist loses `core/config/bootstrap/db_bootstrap.py`.
- **Mutants**: drop the `alembic_version` line; drop one helper from step 1; compile without
  `if_not_exists`.

### CB-3 (closes SF-02, HITL): the dead code — FR-11
- **Red first**: `tests/unit/core/config/test_config_is_pure_logic.py`: `core/config` imports no
  `sqlite3`, `sqlalchemy`, `logging.handlers` or `asyncio`; no `_now_iso` is defined outside
  `commons`.
- Green: the queue, `cqrs_context` and its two uses in the runner, the dead helpers, the four
  `_now_iso` copies; `core/config/database.py` deleted, or reduced to nothing that does I/O.
- The allowlist is empty; the guard keeps the empty set.
- Docs: `src/specweaver/core/CLAUDE.md` (says "Alembic migrations"),
  `docs/dev_guides/special_patterns_and_adaptations.md` §21,
  `docs/dev_guides/domain_driven_cli_creation.md` (a stale `cli_db_utils` path).

## Research Notes

- `bootstrap_database(db_path: str) -> None` (`core/config/bootstrap/db_bootstrap.py:160`) uses
  SQLAlchemy's own `create_async_engine` (:8,168): no foreign keys, no WAL, today.
- `get_db()` (`db_bootstrap.py:197`) swallows a bootstrap failure as a warning (:203); SF-03 changes
  that, so SF-02 keeps `get_db` but lets `bootstrap_database` raise.
- No rename from the pre-`TECH-005` names (`projects`, `active_state`, `project_standards`,
  `artifact_events`) exists in today's bootstrap. Only Alembic script `af60fd3509a2` had one, and
  nothing ever ran it. A file from before 2026-07-12 (`3d347209`) today gets new empty tables beside
  its old ones.
- `StrictISODateTime` is used by `workspace/store.py` (3 columns) and `workspace/memory/store.py` (9).
- `price_refresh.py:162,260`: `create_engine("sqlite://", creator=db.connect)`.

## Decisions (Phase 4, the user, 2026-11-07)

- **Files from before 2026-07-12 are refused, not renamed** `[agreed 2026-11-07]`: no real
  SpecWeaver database is in use, so no such file exists. Before step 1, `adopt` finds any of
  `projects`, `active_state`, `project_standards`, `artifact_events` and stops, naming the file and
  saying it was made before 2026-07-12 and cannot be brought forward. FR-6 compares a new file with
  one the release before this ticket made.
- **A failed price seed stays a warning** `[agreed 2026-11-07]`: it is data, not schema.
- The import change runs by script, checked by `git diff --stat`, a grep and the suite; no
  re-export stays behind.

## Red/Blue (Phase 5), 2 cycles

Cycle 1: (HIGH) the old-name refusal must run before step 1 creates the new tables, or the next open
would see both names and pass: it is `adopt`, inside step 1's transaction. (MEDIUM) a test patches
`specweaver.core.config.database.Database._ensure_schema` (`tests/unit/interfaces/cli/test_cli_helpers.py:26`)
with `create=True`, so it would pass silently after the move: it is rewritten in CB-1. (MEDIUM)
`Database.sync_engine()` must use `NullPool` and the same pragmas as the async engine: it builds on
`open_sqlite` as its `creator`. Cycle 2: none above threshold.
