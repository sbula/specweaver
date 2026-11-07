# Design: The Database Is Opened Three Ways, and the API Server Skips Migrations

- **Feature ID**: TECH-090
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED (the user, 2026-11-07)
- **Kind**: `bugfix`
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_design.md
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`; 8 findings. Re-measured
  2026-11-07 before this design; the user moved it ahead of `A-SENS-02`, which plugs Postgres into
  the one way of opening a database `[agreed 2026-11-07]`.

## Feature Overview

TECH-090 gives SpecWeaver one way to open its SQLite files. A new package
`infrastructure/database/` opens all four files, the config database, the pipeline state, a
project's graph and its reservations, with the same settings everywhere: WAL, foreign keys, and a
wait for a locked file `[agreed 2026-11-07]`. Each file records its schema version in
`PRAGMA user_version`, and one routine runs only the missing steps, each in one transaction
`[agreed 2026-11-07]`. The CLI and the API run that same routine before they use a file, and a
failed step stops them instead of warning `[agreed 2026-11-07]`. Alembic, which nothing ran, is
removed, and so are a write queue nothing writes to and four private timestamp copies. It does not
build Postgres: `A-SENS-02` adds a second backend at this one place.

## The Defect (measured 2026-11-07)

The audit's line numbers had drifted, and one claim was wrong: the CLI runs no migrations. It runs
hand-written schema code, and nothing runs Alembic.

| Finding | Measured |
|---|---|
| CW-5: "pure-logic" config owns I/O | `core/config/context.yaml:11` `archetype: pure-logic`; `core/config/database.py` holds the async engine factory (:175), `session_scope` with a semaphore per loop (:157-208), `CQRSQueueManager` (:64-154) and a `RotatingFileHandler` writing `.dead_letter.log` in the working folder (:76, :123) |
| CW-6: dead code | nothing calls `enqueue`; `core/flow/engine/runner.py:195,252` only start and stop the empty queue (`cqrs_context`); `database.py:248-262` (`_PROJECT_NAME_RE`, `_now_iso`, `_validate_project_name`) has no caller |
| CW-7: one file, many openers | `specweaver.db` is opened 4 ways: `Database.connect()` (sqlite3, WAL + FK, `database.py:277`), `async_session_scope()` (FK, no WAL, :285), `db_bootstrap.py:168` (raw `create_async_engine`: no FK, no WAL), `price_refresh.py:162,260` (sync engine over `db.connect`). `pipeline_state.db`, `graph.db` and `reservations.db` each have their own opener: 7 ways in all |
| Pragmas differ | busy_timeout: graph 5 s, lineage 30 s, the rest none; foreign keys: off in `reservation.py:25` and the bootstrap engine; WAL: off in the async and bootstrap engines (WAL is stored in the file, so a new file first opened by them has none) |
| CW-7: bridges | `commons/async_bridge.run_sync` (used by the bootstrap) and `cli_kit/_core.run_repo_op` (`anyio.run`) |
| CW-21 | `workspace/store.py` (517 lines) mixes ORM models, raw SQL and a repository; the memory tables register only by side-effect imports (`db_bootstrap.py:10`, `alembic/env.py`) |
| X-14 | `_now_iso` copies at `core/config/database.py:251`, `workspace/store.py:24` (both dead), `core/flow/engine/store.py:474`, `graph/lineage/store/lineage_repository.py:12`; `commons/timestamps.now_iso` exists |
| FL-19 | the legacy-table rename is written three times (`core/flow/engine/store.py:128`, `reservation.py:29`, `graph/core/store/repository.py:50`); the reservations path twice (`gates.py:111`, `sandboxed_execution.py:144`) |
| EP-10, defect 4 | every `sw` command reaches the bootstrap through `get_db()` (`db_bootstrap.py:197`), up to three times, and a failure is only `logger.warning` (:203); `interfaces/api/app.py:93` and `api/deps.py` open the file with no bootstrap and no `setup_logging`; `sw serve` gets both only through the CLI callback |
| Alembic | `alembic.ini` points at `sqlite+aiosqlite:///alembic_test.db`; no source calls Alembic; its first script expects pre-`TECH-005` table names and fails on any current database (`NoSuchTableError: active_state`, measured) |
| `--help` reads the database | `interfaces/cli/main.py:40` reads the active project before every subcommand, `sw run --help` included |

## Path List (`ADR-005`)

| # | Path | Span | Owner | Status |
|---|---|---|---|---|
| P-1 | `sw <command>` on a fresh machine → the schema routine → the command runs on a current schema | CLI, opener | TECH-090 (FR-1..FR-3, FR-7) | ⬜ |
| P-2 | `sw serve` or `create_app()` on a fresh machine → the same routine → the API answers on a current schema | API, opener | TECH-090 (FR-7) | ⬜ |
| P-3 | a database from an old release → upgrade → the same schema as a new one, except 4 listed defaults | opener, schema steps | TECH-090 (FR-4..FR-6) | ⬜ |
| P-4 | one process holds the write lock → the CLI waits up to 30 s; the API waits 5 s, then `503` with `Retry-After: 1` | CLI, API, opener | TECH-090 (FR-2, FR-9) | ⬜ |
| P-5 | `sw --help`, `sw --version`, `sw <command> --help` with a broken database → the help shows | CLI | TECH-090 (FR-8) | ⬜ |
| P-6 | `A-SENS-02` adds Postgres → one new backend at the opener; no caller changes | opener | `A-SENS-02` | not built here |

## Research Findings

### Codebase Patterns

- **Callers.** `Database` is used in 21 source files and 132 test files; `bootstrap_database` in 1
  source file and 122 test files; `async_session_scope` at 20 source call sites. The move is wide but
  mechanical.
- **Schema code today.** `bootstrap_database` (`db_bootstrap.py:160`) runs `create_all` for three
  metadata sets, then ten idempotent helpers (`_allow_unknown_cost`, `_add_history_columns`,
  `_add_call_status`, `_add_cached_columns`, `_add_refresh_reached`, `_add_console_log_level`,
  `_move_default_dal_once` with its `specweaver_migrations` marker, `_drop_retired_llm_tables`,
  `_add_price_index`, `_seed_prices`). These become the baseline steps.
- **Pipeline state.** `StateStore._ensure_schema` (`core/flow/engine/store.py:161`) keeps
  `flow_state_schema_version`: v1→v2 adds `parent_run_id`, v2→v3 adds a table the
  `IF NOT EXISTS` script already makes, v3→v4 adds `spend_state`; a new file records v4.
- **The 4 old defaults.** `workspace/store.py:51-65` sets `log_level`, `auto_bootstrap_constitution`,
  `stitch_mode`, `default_dal` by ORM `default=` only; the only insert path, `register_project`
  (:154-178), relies on it. Old Alembic-made files carry SQL defaults for the same columns
  (`037b85034bb0`, :278-311). So the code sets the values itself, and the difference is cosmetic.
- **Boundaries.** `graph/context.yaml` forbids `core/config`; the opener therefore may not live
  there or depend on it. `tach.toml` has no `specweaver.infrastructure` module and is `exact`.
- **The Alembic scripts against today's schema** (2026-11-07, at the user's request): every index,
  NOT NULL, foreign key and memory table they make is in today's schema; the rest touches the four
  LLM tables today's code drops on purpose (`_RETIRED_LLM_TABLES`). Deleting them loses nothing.
- **Guides that name the old way**: `docs/dev_guides/domain_driven_cli_creation.md:46,120`
  (`get_db`, a stale `cli_db_utils` path), `special_patterns_and_adaptations.md` §21 (the CQRS
  session factories).

### Red/Blue (Phase 6), 2 cycles

Cycle 1: (HIGH) FR-12 was never asked in the grilling: put to the user at approval. (HIGH) FR-7 said
"before first use" for files a door never opens: the doors open the config database and the state;
a project's files run their steps when first opened. (MEDIUM) two processes on a fresh machine could
both run a step: `BEGIN IMMEDIATE` and a second read of the version (FR-3). (MEDIUM) the opener cannot
know its door: AD-5. (MEDIUM) `503` only for a lock (FR-9). (MEDIUM) "oldest known state" named two
fixtures (FR-6). (MEDIUM) the lineage repository opens `specweaver.db` too: in SF-02. (LOW) step 1
must stay idempotent for files at version 0 (FR-5). (LOW) lazy project changes log levels of
project-free commands (AD-4). Cycle 2: (MEDIUM) AD-5 is process state; tests reset it in a fixture.
(LOW) CLI and API in two processes rotating one log file: FR-12 writes the API's own file. Below
threshold.

### External Tools

| Tool | Fact | Source |
|---|---|---|
| SQLite | `journal_mode` is stored in the file and cannot change inside a transaction; `foreign_keys` is per connection and a no-op inside a transaction; `busy_timeout` is per connection; `user_version` is in the file header | sqlite.org/pragma.html |
| SQLite | `user_version`, `CREATE`, `DROP`, `ALTER` inside one `BEGIN … COMMIT` roll back together | to be proven by FR-4's test, not assumed `[agreed 2026-11-07]` |
| Python `sqlite3` | in legacy mode DDL and PRAGMA run outside a transaction unless `BEGIN` is issued; `executescript` commits first; `autocommit=` exists only from 3.12 | docs.python.org/3/library/sqlite3.html |
| SQLAlchemy 2.x + aiosqlite | pragmas through `event.listens_for(engine.sync_engine, "connect")`; transactional DDL needs `isolation_level=None` and a `"begin"` event issuing `BEGIN` | docs.sqlalchemy.org/en/20/dialects/sqlite.html |
| Click / Typer | the group callback runs before the subcommand parses `--help` | click `Group.invoke` |
| HTTP | `Retry-After` with `503` | RFC 9110 §10.2.3 |

### Blueprint References

`user_version` step lists as in Android's `SQLiteOpenHelper` and `sqlite-migrate`: one step per
version, one transaction per step, refuse a file newer than the code.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | `infrastructure/database/` SHALL be the only code that opens `specweaver.db`, `pipeline_state.db`, `graph.db` and `reservations.db`, for sync connections and async engines alike `[agreed 2026-11-07]` | any module | open a file | it gets the connection from the opener; a guard test fails on any `sqlite3.connect`, `create_engine` or `create_async_engine` elsewhere in `src` |
| FR-2 | Every connection the opener makes SHALL have WAL, foreign keys on, and a lock wait of 30 s for the CLI and 5 s for the API `[agreed 2026-11-07]`; the door sets the wait once for its process (AD-5) | CLI, API | open a file | `PRAGMA journal_mode`, `foreign_keys` and `busy_timeout` read back as set, on each of the 4 files, sync and async |
| FR-3 | Each file SHALL carry its schema version in `PRAGMA user_version`, with an ordered step list per file; each step and its version change commit in one `BEGIN IMMEDIATE` transaction, and the version is read again after the lock, so two processes never apply a step twice; a file newer than the code is refused, naming the file and both versions `[agreed 2026-11-07]`; the opener runs a file's steps the first time a process opens it | the schema routine | open a file | only the missing steps run; a second run changes nothing; two processes starting together end at the same version; a newer file stops with the message |
| FR-4 | `pipeline_state.db`'s `flow_state_schema_version` v1..v4 SHALL map to `user_version` through an explicit table, in one transaction: read the old value, set `user_version`, check it, then drop the old table `[agreed 2026-11-07]` | the schema routine | open an old file | test files at v1, v2, v3 and v4 each end at the mapped version with their rows; a rollback in the middle leaves the old table and version |
| FR-5 | `specweaver.db`'s steps SHALL start from today's schema code as step 1, whose parts stay idempotent so a file from before this ticket (`user_version` 0) runs it safely, and drop a leftover `alembic_version` table `[agreed 2026-11-07]` | the schema routine | open a file | a new file and an old one reach the same version; no `alembic_version` remains |
| FR-6 | A new file and one upgraded from the release before this ticket SHALL have the same schema; a file with the pre-`TECH-005` table names is refused, not renamed, because no real database is in use `[agreed 2026-11-07]`: tables, columns, types, indexes, defaults; the one allowed difference is the SQL defaults of `log_level`, `auto_bootstrap_constitution`, `stitch_mode`, `default_dal` in old files, listed with the reason `[agreed 2026-11-07]` | the schema test | compare | any other difference fails the test |
| FR-7 | The CLI and the API SHALL run the same schema routine on each file before the first work of the command that uses it: the config database and the pipeline state when such a command or the server starts, `reservations.db` in the run setup before the first step (created there if missing), `graph.db` at the start of `sw graph build` `[agreed 2026-11-07]`; a failed step stops the command or the server start, naming the file and the step `[agreed 2026-11-07]` | CLI, API | start | no warning-and-continue; `create_app()` called directly runs it too |
| FR-8 | `sw --help`, `sw --version` and `sw <command> --help` SHALL open no database; the main command reads the active project only when a subcommand needs it `[agreed 2026-11-07]` | user | ask for help | the help shows even when the database file is broken; red first |
| FR-9 | An API request that finds the file locked after 5 s SHALL get `503` with `Retry-After: 1` and no SQL in the body; any other database error stays `500` `[agreed 2026-11-07]` | API client | call while another process holds the write lock | `503`, `Retry-After: 1`; the test really holds the lock |
| FR-10 | Alembic SHALL be gone: `alembic.ini`, `alembic/`, `tests/unit/alembic/`, the `alembic` dependency `[agreed 2026-11-07]` | — | — | no file, test or dependency names it |
| FR-11 | `core/config` SHALL hold no engine, queue or file I/O, so its `pure-logic` archetype is true; the write queue, `cqrs_context`, the dead-letter log, the dead helpers and the four `_now_iso` copies are deleted; `commons/timestamps.now_iso` stays `[agreed 2026-11-07]` | — | — | a guard test fails on a `_now_iso` definition outside `commons`; `core/config` imports no `sqlite3`, `sqlalchemy` engine or `logging.handlers` |
| FR-12 | `create_app()` SHALL set up logging as the CLI does (EP-10) `[agreed 2026-11-07]` | API | start | the API writes its log where the CLI writes its own |
| FR-13 | `workspace/store.py` SHALL be split into its ORM models, its synchronous lookups and its repository, and `specweaver.db`'s step 1 SHALL name the memory tables it creates instead of registering them by a side-effect import (CW-21) `[agreed 2026-11-07]` | — | — | no module imports a store only for its side effect; each part has one reason to change; the schema comparison (FR-6) still passes |
| FR-14 | The known clones in the store, database and API code this ticket touched SHALL be gone, 11 of 12; the twelfth, the header and imports shared by `api/v1/constitution.py` and `standards.py`, is no code copy and stays `[agreed 2026-11-07]`; `flow_artifact_events` gets one writer, `graph.lineage`'s `LineageRepository` `[agreed 2026-11-07]`: `workspace/store.py`, `workspace/memory/store.py`, `core/flow/store.py` with the lineage repository, `api/v1/pipelines.py`, `api/v1/projects.py`, the CLI display with the API event bridge; the test helpers that read and set `user_version` live once in `tests/fixtures/db_utils.py` `[agreed 2026-11-07]` | — | — | the duplication baseline loses those 11 entries (86 → 75) and gains none; the other clones stay with the modules that own them |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | the four file paths | `core/config/paths.py` `config_db_path()`, `state_db_path()`; `project_path / ".specweaver" / "graph.db"` (`graph/core/builder/orchestrator.py:247`), `"reservations.db"` (`gates.py:111`) | read the files |
| FR-3 | today's steps | `bootstrap_database(db_path: str) -> None` and its helpers, each `(conn: Connection)` | read `db_bootstrap.py:34-160` |
| FR-4 | the old version | `flow_state_schema_version` rows, `MAX(version)` | read `core/flow/engine/store.py:161` |
| FR-7 | the CLI door | `interfaces/cli/main.py:40` `_app_callback`, `cli_kit/_core.get_db` | read the files |
| FR-7, FR-9, FR-12 | the API door | `interfaces/api/app.py:88` `create_app`, `api/deps.py:28` `get_db` | read the files |
| FR-12 | logging | `telemetry_logger.setup_logging(project_name=..., level=..., console_level=...)` | read `interfaces/cli/main.py:66` |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | No data is lost | every row of an old file survives its upgrade (FR-4, FR-6 fixtures); otherwise behaviour stays the same and the suite passes |
| NFR-2 | The opener depends on nothing in SpecWeaver | `infrastructure.database` `depends_on = []` in `tach.toml`, archetype `adapter`; callers pass their path and lock wait, so `graph` may use it |
| NFR-3 | Postgres is not built | the opener takes a file path; `A-SENS-02` adds its backend there (P-6) |
| NFR-4 | Help stays fast | FR-8: no database open, no schema routine |

## External Dependencies

None new. `alembic` is removed from `pyproject.toml` and `uv.lock` (FR-10).

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | The opener lives in `infrastructure/database/`, an `adapter` beside `infrastructure/llm/` `[agreed 2026-11-07]` | `core/config` stays `pure-logic`; `graph` may not depend on `core/config` | Yes, agreed |
| AD-2 | Schema versions in `PRAGMA user_version`, one step list per file, no Alembic `[agreed 2026-11-07]` | Alembic never ran; `A-SENS-02` adds it back from a proven starting state | Yes, agreed |
| AD-3 | Each module keeps its own tables and step list; the opener owns only how a file is opened and how steps run | one place for settings, no central schema | No |
| AD-4 | The CLI reads the active project lazily, in the commands that need it | FR-8; the callback today reads it for the log levels, so a command that needs no project now logs at the default levels | No |
| AD-5 | The lock wait is a process setting the door sets once (CLI 30 s, API 5 s); the opener reads it, so a deep caller such as the graph repository needs no door knowledge `[agreed 2026-11-07]` | FR-2 without passing a number through every layer | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| The opener and the step runner | medium | medium: transactions around DDL in `sqlite3` legacy mode |
| Moving 4 files' callers | large but mechanical (~21 source, ~130 test files) | low |
| The `pipeline_state.db` version move | small | medium: it cannot be undone, hence FR-4's fixtures |
| The doors | small | low |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| `A-SENS-02` | one place to add Postgres, and a proven schema to start from | high |
| API users | the server never runs on an old schema; a lock answers `503`, not a hang | medium |
| Maintainers | one set of settings; no dead queue; no Alembic that looks real | medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| A user's old database fails to upgrade | low | high | fixtures for every known old state; a failed step stops before damage (FR-3, FR-7) |
| A transaction does not cover the DDL | medium | high | FR-4's rollback test |
| A long-running test suite relies on the warning path | low | low | the suite runs at every commit |

### Refactoring Opportunities
`workspace/store.py`'s split (CW-21) into models, raw SQL and repository was planned for SF-02 but
not done there; SF-04 does it (FR-13) `[agreed 2026-11-07]`.

## Non-Goals

- Postgres, Apache AGE, pgvector: `A-SENS-02`.
- A live switch between backends.
- `TECH-088`'s graph-engine merge; if it retires `graph.db`, one file leaves FR-1's list.
- The SQL defaults of old files are not rebuilt away (FR-6) `[agreed 2026-11-07]`.
- The 74 other clones in the duplication baseline, and the import-only clone of FR-14: they stay with the modules that own them (FR-14) `[agreed 2026-11-07]`.

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `docs/dev_guides/domain_driven_cli_creation.md` | how a CLI gets the database | ⬜ To be updated during Pre-commit |
| `docs/dev_guides/special_patterns_and_adaptations.md` §21 | the async pragmas, without the CQRS queue | ⬜ To be updated during Pre-commit |
| `docs/dev_guides/working_in_this_repo.md` | how to add a schema step | ⬜ To be updated during Pre-commit |

## Sub-Feature Breakdown

### SF-01: One opener, versioned steps
- **Scope**: `infrastructure/database/` with the sync opener, the async engine factory, the step runner
  and the one legacy-rename helper; `pipeline_state.db`, `graph.db` and `reservations.db` move onto it.
- **FRs**: [FR-1 (three files), FR-2, FR-3, FR-4]
- **Inputs**: today's openers
- **Outputs**: the opener and the step runner
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_sf01_implementation_plan.md

### SF-02: The config database on the opener
- **Scope**: `Database` and the bootstrap move to the opener; today's schema code becomes the
  baseline steps; the lineage repository (`graph/lineage`), which opens the same file, moves too;
  the schema comparison; Alembic and the dead code go.
- **FRs**: [FR-1 (`specweaver.db`), FR-5, FR-6, FR-10, FR-11]
- **Inputs**: SF-01's opener and step runner
- **Outputs**: one config-database opener
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_sf02_implementation_plan.md

### SF-03: The doors
- **Scope**: the CLI and the API run the routine and stop on failure, `reservations.db` in the run
  setup and `graph.db` at the start of `sw graph build`; lazy active project; the API's
  `503` and its logging.
- **FRs**: [FR-7, FR-8, FR-9, FR-12]
- **Inputs**: SF-02's routine
- **Outputs**: P-1, P-2, P-4, P-5 walked
- **Depends on**: SF-02
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_sf03_implementation_plan.md

### SF-04: One copy of each block
- **Scope**: the CW-21 split of `workspace/store.py`; the memory tables named in step 1; the 12
  clones in the store, database and API code this ticket touched; the test helpers in one place.
- **FRs**: [FR-13, FR-14]
- **Inputs**: SF-03's doors
- **Outputs**: the duplication baseline without those entries
- **Depends on**: SF-03
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-090/TECH-090_sf04_implementation_plan.md

## Execution Order

SF-01 → SF-02 → SF-03 → SF-04. Each is one commit chain; the last boundary of each is the user's acceptance.

## Live Demo

Run 2026-11-07 on a fresh data dir (`SPECWEAVER_DATA_DIR` in a temp folder):

```bash
sw run --help                 # exit 0, and still no database file
sw init demo --path ./demo    # specweaver.db at user_version 1
# PRAGMA user_version = 99 on specweaver.db
sw projects                   # "…/specweaver.db is at schema version 99, but this SpecWeaver knows
                              #  only up to 1; update SpecWeaver to open it", exit 1
sw --help                     # exit 0 on the same file
# a second connection holds BEGIN IMMEDIATE; create_app(); POST /api/v1/projects/demo/use
#   → 503, Retry-After: 1, {"detail": "The database is busy. Retry.", "error_code": "DATABASE_BUSY"}
```

No model is called, so the nightly real-model run has nothing to add; the same journeys run in
`tests/e2e/capabilities/interfaces/test_fresh_machine_cli_e2e.py`,
`test_fresh_machine_api_e2e.py` and `tests/integration/interfaces/api/test_api_busy_database.py`.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | One opener, versioned steps | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | The config database on the opener | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | The doors | SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-04 | One copy of each block | SF-03 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Grilling 2026-11-07** (the user), three rounds, Q1-Q12: one opener for all 4 files, in
`infrastructure/database/`; `user_version` per file; a failed step stops; WAL and 30 s (CLI) / 5 s
(API); Alembic deleted after the scripts were checked against today's schema; `503` with
`Retry-After: 1`; the `pipeline_state.db` version move by explicit map in one transaction; the
leftover `alembic_version` dropped; a schema comparison with the 4 old defaults as the one listed
exception. Each decision sits beside its fact above.
At approval the user asked where `graph.db` and `reservations.db` are first opened: `reservations.db`
at a gate after a step had run, so FR-7 now prepares it in the run setup (Q13) `[agreed 2026-11-07]`.
**Design approved 2026-11-07** (the user), FR-12 and AD-4/AD-5 included.
**SF-01 plan approved 2026-11-07** (the user).
**SF-01 dev 2026-11-07**: CB-1 `9b03b250`, CB-2 `de177b8d`, CB-3 accepted by the user 2026-11-07;
the two silent mutants (map 4 → 0, no read-back) judged equivalent by the user.
**SF-02 plan approved 2026-11-07** (the user): files with the pre-`TECH-005` names are refused; a failed price seed stays a warning.
**SF-02 dev 2026-11-07**: CB-1 `58632d7a`, CB-2 `7dcc47b9`, CB-3 `6b6e58c9` accepted by the user
2026-11-07. B-INTL-09 FR-6's Alembic half no longer applies; its foreign-key half is proven by
`test_session_scope.py`.
**SF-03 plan approved 2026-11-07** (the user): the API logs to `logs/_api/`; a CLI command switches to its
project's log at its first database use; the `503` body carries `error_code` `DATABASE_BUSY`.
**SF-03 dev 2026-11-07**: CB-1 `94a945a3`, CB-2 `c15cac35`, CB-3 accepted by the user 2026-11-07. A
command's lines before its first database use go to the `_global` log (Q2).
**SF-04 added 2026-11-07** (the user, before sign-off): the CW-21 split the design had promised for
SF-02 was never done; the user chose to do it here, with the 12 clones in the code this ticket
touched and the test helpers (FR-13, FR-14); the other 74 clones stay out.
**SF-04 plan approved 2026-11-07** (the user): one writer for `flow_artifact_events`; the import-only clone stays;
`workspace/models.py` and `workspace/lookups.py`.
**SF-04 dev 2026-11-07**: CB-1 `d7a0bdc7`, CB-2 `cbe96d4e`, CB-3 accepted by the user 2026-11-07; the
duplication baseline is 75 (86 − 11).
**Next step**: the TECH-090 closure gate (`specweaver-feature` Phase 4), then the user's sign-off.
**If resuming mid-feature**: read the Progress Tracker above. Find the first ⬜ and resume from
there using the appropriate skill.
