# Database Schema Versions

**What:** every SpecWeaver SQLite file carries its schema version in `PRAGMA user_version`, and the
module that owns the file keeps an ordered list of numbered steps (`TECH-090`).

**Why:** follows the Bounded Contexts architecture: a domain changes its schema without touching
another domain's models, and one place (`infrastructure/database/`) decides how a file is opened
and how steps run.

## How a file is brought up to date

```mermaid
graph TD
    Door[CLI or API door] -->|opens| Opener(infrastructure/database: open_sqlite)
    Opener -->|WAL, foreign keys, lock wait| File[(SQLite file)]
    Owner[owning module: its Step list] -->|upgrade| Runner(infrastructure/database: upgrade)
    Runner -->|reads user_version, runs missing steps| File
```

| File | Owner of the steps |
|---|---|
| `~/.specweaver/specweaver.db` | `core/config/bootstrap/db_bootstrap.py` |
| `~/.specweaver/pipeline_state.db` | `core/flow/engine/store.py` |
| `<project>/.specweaver/graph.db` | `graph/core/store/repository.py` |
| `<project>/.specweaver/reservations.db` | `core/flow/engine/reservation.py` |

| File | Brought up to date |
|---|---|
| `specweaver.db` | a command's first database use (`cli_kit/_core.get_db`); help and `--version` open none; the API in `create_app` |
| `pipeline_state.db` | `sw run` and `sw resume`, before the runner starts; the API in `create_app` |
| `graph.db` | `sw graph build`, before any file is read |
| `reservations.db` | the run setup (`build_run`), before the first step; created if missing |

A file that cannot be opened, is newer than the code, or whose step fails raises a `SchemaError`
naming the file; the CLI prints it and exits 1, and `create_app` raises it, so no server starts.
An API request that finds a file locked after the API's 5 s wait answers `503` with
`Retry-After: 1` (`interfaces/api/errors.py`).

- Each step and its version change commit in one `BEGIN IMMEDIATE` transaction; the version is
  read again once the lock is held, so two processes never apply a step twice.
- A file newer than the code is refused, naming the file and both versions.
- A step that has shipped is never edited; a change is a new step at the end.
- How to add one: `docs/dev_guides/working_in_this_repo.md` trap 12.

Alembic was removed in `TECH-090`: nothing ever ran it, and its scripts could not run on any
current database.
