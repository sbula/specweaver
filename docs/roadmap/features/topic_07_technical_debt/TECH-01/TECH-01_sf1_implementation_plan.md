# Implementation Plan: Domain-Driven Design Unification [SF-1: Deconstruct Config Monolith]

- **Feature ID**: TECH-01
- **Sub-Feature**: SF-1 — Deconstruct Config Monolith
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-01/TECH-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-01/TECH-01_sf1_implementation_plan.md
- **Status**: COMPLETED (Phase 3 tests passed autonomously, Phase 4 & 5 green)

## Overview
Deconstruct the monolithic `core/config/database.py` and `_schema.py` raw SQLite strings into feature-bounded contexts (`llm/`, `flow/`, `workspace/`). Implement a highly concurrent `AsyncSession` architecture powered by SQLite WAL mode, `NullPool`, and an asynchronous Command Query Responsibility Segregation (CQRS) Write Queue to safely support massive orchestrator parallelism without OS File Descriptor exhaustion or SQLite locking.

> [!CAUTION]
> **Zero Regression Warning:** All new SQLAlchemy models MUST mathematically map to the exact column names and types defined in the legacy `_schema.py` raw SQL strings to prevent breaking the existing `specweaver.db` files of our users.

## Proposed Changes

### 1. Dependencies
#### [MODIFY] pyproject.toml
- Add `sqlalchemy[asyncio]>=2.0.0`, `aiosqlite>=0.20.0`, and `alembic>=1.13.0` to the `dependencies` array.

### 2. Core Infrastructure Refactor [COMPLETED]
#### [MODIFY] src/specweaver/core/config/database.py
- [x] Remove all raw `sqlite3` connection logic and mixin inheritance.
- [x] Implement `StrictISODateTime(TypeDecorator)` to guarantee SQLite timestamps exactly match the legacy `datetime.now(tz=UTC).isoformat()` format, preventing Zero Regression crashes.
- [x] Implement `CQRSQueueManager`: an `asyncio.Queue` initialized with `maxsize=1000` to prevent OOM crashes.
- [x] Implement a Write Worker with a Dead Letter Exchange (DLX) `try/except` loop. If an insert fails, it writes to `.dead_letter.log` (configured via `logging.handlers.RotatingFileHandler` with 10MB max size and 3 backups) and continues, guaranteeing the worker never dies and poisons the queue and preventing disk exhaustion.
- [x] **Constraint**: The `CQRSQueueManager` MUST process pure DTO payloads (not callbacks capturing caller sessions). The worker loop MUST instantiate its own isolated `session_scope` to execute the writes to prevent `DetachedInstanceError`s.
- [x] Implement `session_scope()`: an async context manager that yields a **read-only** `AsyncSession` powered by `aiosqlite`.
- [x] **Constraint**: Wrap the internal yield of `session_scope` with an `asyncio.Semaphore(500)`. This guarantees we never exceed OS File Descriptor limits under massive concurrency.
- [x] **Constraint**: Configure the SQLAlchemy async engine to use `poolclass=NullPool`. Disabling the pool entirely prevents `QueuePool overflow` crashes.
- [x] Implement `cqrs_context`: an asynchronous context manager (`async with`) whose `__aexit__` blocks and flushes the queue, guaranteeing telemetry writes even during unhandled Python exceptions.
*(Deviation: Renamed CQRSQueue to CQRSQueueManager and CQRSContext to cqrs_context for convention matching)*

### 3. Domain Stores (The Bounded Contexts)
#### [NEW] src/specweaver/llm/store.py
- Define a `DeclarativeBase`. Use `@declared_attr` to prefix tables (e.g. `__tablename__ = f"llm_{cls.__name__.lower()}"`).
- Migrate `llm_profiles`, `project_llm_links`, `llm_usage_log`, and `llm_cost_overrides` from `_schema.py` into native SQLAlchemy models.
- Port the CRUD methods from `_db_llm_mixin.py` and `_db_telemetry_mixin.py` into an `LlmRepository` class that accepts an `AsyncSession`.
- **Constraint**: Write methods (like `log_usage`) must pass pure DTOs to the global write queue.

#### [NEW] src/specweaver/flow/store.py
- Define a `DeclarativeBase`.
- Migrate the `artifact_events` table into a native SQLAlchemy model.
- Port CRUD logic into a `FlowRepository`.
- **Constraint**: `log_artifact_event` must pass pure DTOs to the global write queue.

#### [NEW] src/specweaver/workspace/store.py
- Define a `DeclarativeBase`.
- Migrate the `projects`, `active_state`, and `project_standards` tables into native SQLAlchemy models.
- Port CRUD methods from `_db_config_mixin.py` and `_db_extensions_mixin.py` into a `WorkspaceRepository`.

### 4. Monolith Cleanup
#### [DELETE] src/specweaver/core/config/_schema.py
#### [DELETE] src/specweaver/core/config/_db_llm_mixin.py
#### [DELETE] src/specweaver/core/config/_db_telemetry_mixin.py
#### [DELETE] src/specweaver/core/config/_db_extensions_mixin.py
#### [DELETE] src/specweaver/core/config/_db_config_mixin.py

### 4b. Dependency Inversion (The Monolith Fix)
#### [MODIFY] src/specweaver/core/config/database.py
- Delete `_ensure_schema`, `register_project`, `get_project`, `list_projects`, `remove_project`, `update_project_path`, `get_active_project`, `set_active_project`.
- Delete ALL inline imports of `LlmProfile`, `WorkspaceRepository`, etc.
- `Database` class must strictly serve as a connection provider (`create_async_engine`, `session_scope`, `CQRSQueueManager`).

#### [MODIFY] src/specweaver/infrastructure/llm/router.py & factory.py
- Refactor `ModelRouter.__init__` and `create_llm_adapter` to completely drop the `db: Database` parameter and `load_settings` imports.
- They MUST accept pure `SpecWeaverSettings` (or a `SettingsProvider` closure) injected by the CLI layer, fully decoupling `llm` from DB/Workspace active-project logic.

#### [MODIFY] src/specweaver/core/config/settings.py
- Extract `load_settings`, `load_settings_for_active`, and `migrate_legacy_config` into a new CLI-owned module, leaving only the Pydantic data structures in `config/settings.py`.

#### [NEW] src/specweaver/interfaces/cli/settings_loader.py
- House the newly extracted `load_settings` and `migrate_legacy_config` logic here, allowing it to legally import from `workspace` and `llm` according to architecture rules.

#### [NEW] src/specweaver/interfaces/cli/_db_utils.py
- Implement the `_ensure_schema` logic here. Uses safe, idempotent `run_sync(Base.metadata.create_all)` natively. 
- **Constraint**: Absolutely NO programmatic `alembic.command.upgrade` calls at runtime. Alembic is reserved for explicit developer CLI migrations.

#### [MODIFY] src/specweaver/interfaces/cli/*.py (All Handlers)
- Update `projects.py`, `standards.py`, `usage_commands.py`, etc., to stop using `db.get_active_project()`. Instead, use `async with db.async_session_scope() as session:` to instantiate `WorkspaceRepository` natively and retrieve data.

### 4c. Formalize Workspace Boundary (NFR-2)
#### [NEW] src/specweaver/workspace/context.yaml
- Define the `workspace` archetype, explicitly forbidding `interfaces/*` and `workflows/*` but allowing `core.config`.
#### [MODIFY] tach.toml
- Add `{ path = "src.specweaver.workspace", depends_on = ["src.specweaver.core.config"] }` to the `modules` array to guarantee architectural enforcement.

### 5. Alembic Migration Engine
#### [NEW] alembic.ini
- Standard Alembic configuration pointing to `alembic/versions`.
#### [NEW] alembic/env.py
- Import `llm.store.Base`, `workspace.store.Base`, and `flow.store.Base`.
- **Constraint**: Ensure `store.py` files have ZERO top-level imports of runtime application state so Alembic can boot them safely in isolation.
- Combine their metadata: `target_metadata = [Base.metadata for Base in ...]`
- *Note: Since there are no live production customers yet, we will use standard Alembic generation without artificially shielding legacy SQLite tables from drops.*

### 6. Orchestrator Lifecycle [COMPLETED]
#### [MODIFY] src/specweaver/flow/runner.py
- [x] Wrap the main orchestration execution logic inside `async with cqrs_context():`. This guarantees the database queue flushes correctly as the event loop unwinds.

## Verification Plan

### Automated Tests
1.  Run `sw check` to ensure no architectural boundary rules (`tach`) are violated.
2.  Run `pytest tests/` — **NFR-1 (Zero Regression)** demands that 100% of the existing test suite passes without changing any test assertions.
3.  Run Alembic autogenerate to verify it detects zero schema drift against a legacy `specweaver.db` created by the old `_schema.py` strings.
