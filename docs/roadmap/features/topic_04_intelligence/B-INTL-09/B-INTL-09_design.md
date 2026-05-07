# Design: Agent Memory Bank

- **Feature ID**: B-INTL-09
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_design.md
- **Absorbs**: Former `C-EXEC-05` (Issue Tracker Atoms) and `B-INTL-10` (Agentic Workflow State Ledger)
- **SF-1 Status**: 🟢 Completed
- **SF-2 Status**: 🟢 Completed
- **SF-3 Status**: 🟢 Completed
- **SF-4 Status**: 🟢 Completed

## Feature Overview

Feature B-INTL-09 is the persistent SQLite backend for the Agent Memory Bank (US-28). It defines `Task`, `Epic`, `TaskDependency` (DAG), `StateTransition`, and `Defect` entities in the `workspace` module, paired with a resilient `MemoryRepository` providing CRUD operations, a formal state machine, Optimistic Concurrency Control, circuit breakers, zombie recovery, and upstream DAG propagation. It solves context degradation and enables seamless task handover between AI Agents by storing session state, active tasks, and blockers in a persistent local SQLite Database with built-in reboot resilience (heartbeats). It integrates directly with the existing CQRS SQLite Engine.

## Research Findings

### Codebase Patterns
- **Database Engine**: SpecWeaver utilizes `sqlalchemy[asyncio]` and `aiosqlite` via a robust CQRS queue in `specweaver.core.config.database`.
- **Domain Boundaries**: According to `architecture_reference.md`, physical project state must reside in the `workspace/` module. The schema must not be placed in `intelligence/` or `graph/`.
- **NetworkX Bottleneck**: The existing Knowledge Graph (`graph` module) was investigated for reuse. It loads the entire dataset into a `networkx.DiGraph` in RAM, which is an architectural anti-pattern for dynamic task tracking and was explicitly rejected.
- **ActiveState Deprecation**: The existing `ActiveState` singleton table is mathematically incapable of supporting a multi-agent fan-out and must be refactored to use the new `worker_id` locking approach.
- **DeclarativeBase Pattern**: The codebase uses **separate `Base(DeclarativeBase)` classes per domain** (`workspace/store.py`, `core/flow/store.py`, `infrastructure/llm/store.py`). New memory models MUST reuse `workspace.store.Base` to share the MetaData registry required for cross-table ForeignKey constraints (e.g., `Task → Project`).
- **PRAGMA Gap**: The existing `create_async_engine()` factory (`database.py:160-172`) does NOT attach a `PRAGMA foreign_keys=ON` event listener. Synchronous `Database.connect()` does (`database.py:265`), but async connections silently ignore FK constraints. This must be fixed for cascade rules to work.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| SQLAlchemy | >=2.0.0 | AsyncSession, DeclarativeBase, event | pyproject.toml |
| aiosqlite | >=0.20.0 | Async connection | pyproject.toml |
| Alembic | * | Migration generation | pyproject.toml |
| Pydantic | * | BaseModel, Field | pyproject.toml |

### Blueprint References
- `US-28` Roadmap definition for Agent-Native Issue & State Tracker.

## Handoff Boundary: B-INTL-09 ↔ D-INTL-06

B-INTL-09 (this feature) and `D-INTL-06` (Context Hydration & Handover) are the two MVS features of US-28. They share the `handover_context` JSON field as their integration surface. The boundary is strictly defined as follows:

| Concern | Owner | Responsibility |
|---------|-------|---------------|
| **Schema definition** (`handover_context` column) | B-INTL-09 | Defines the JSON column on the `Task` model. |
| **Write-side validation** (Pydantic, 8KB limit) | B-INTL-09 | `MemoryRepository` enforces data integrity on WRITE. Rejects malformed or oversized payloads before they enter the DB. Truncates stack traces to last 2000 chars. |
| **Context truncation** (cleanup on ARCHIVED) | B-INTL-09 | Sets `handover_context = NULL` when a task reaches terminal `ARCHIVED` state. |
| **Read-side retrieval** (fetching active context) | D-INTL-06 | Queries the Memory Bank for the current agent's active tasks, blockers, and accumulated context. |
| **Prompt formatting** (injection into LLM system message) | D-INTL-06 | Structures the retrieved context into the LLM prompt template, managing token budgets. |
| **Handover protocols** (when/what to hand over) | D-INTL-06 | Defines the rules for when an agent should save context and how the next agent bootstraps from it. |

> **Rule:** B-INTL-09 ensures only valid, bounded data enters the database. D-INTL-06 ensures the data is correctly retrieved, formatted, and injected into the agent's prompt. Neither feature crosses the other's boundary.

> **Architectural Import Note:** D-INTL-06 must import `MemoryRepository` from `workspace.memory.store`. The `workspace/context.yaml` does not forbid imports from `intelligence/`, and `workspace` is a foundation layer designed to be consumed by higher layers. However, the implementing agent MUST verify this path is allowed by `tach.toml` before writing code.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Schema Definition | System | Define SQLAlchemy models for `Task`, `Epic`, `StateTransition` (with `reason` bounded to `TransitionReason` enum), and `Defect`. Import `Base` from `workspace.store` (do NOT define a new DeclarativeBase). FK links to `projects.name` with explicit `onupdate='CASCADE', ondelete='CASCADE'`. **Task columns:** `id` (UUID PK), `project_name` (FK), `epic_id` (FK nullable), `title`, `description`, `status`, `assigned_worker_id`, `locked_at`, `last_heartbeat_at`, `handover_context` (JSON), `version` (int, OCC), `attempt_count` (int), `created_at`, `updated_at`. **Epic columns:** `id` (UUID PK), `project_name` (FK), `title`, `description` (nullable), `status` (OPEN/CLOSED), `created_at`, `updated_at`. Epic is a grouping container — no state machine, no heartbeat. Task.epic_id is nullable (tasks can exist without an Epic). **TransitionReason enum:** `ACQUIRED`, `RELEASED`, `COMPLETED`, `ZOMBIE_TIMEOUT`, `CIRCUIT_BREAKER`, `MANUAL_UNBLOCK`, `PR_REJECTION`, `UPSTREAM_BLOCKED`, `UPSTREAM_CLEARED`, `AGENT_FAILURE`, `ABANDONED`, `ARCHIVED`. **Indexes:** `idx_task_status_project` on (status, project_name), `idx_task_heartbeat` on (status, last_heartbeat_at), `idx_task_worker` on (assigned_worker_id), `idx_dep_child` on (child_task_id), `idx_dep_parent` on (parent_task_id). | Entities share MetaData registry with Project, are immune to CLI rename wipeouts, and support full audit trails. All hot queries are indexed. |
| FR-2 | DAG Topology | System | Define a `TaskDependency` many-to-many junction table linking `parent_task_id` and `child_task_id`. | A single task can unblock multiple parents, preventing duplicate agent work. |
| FR-3 | Heartbeat Resilience | System | Define `assigned_worker_id`, `status`, `locked_at`, and `last_heartbeat_at` columns on `Task`. | System tracks which agent owns which task to prevent race conditions. |
| FR-4 | Repository API | System | Implement `MemoryRepository` with: transactional OCC `acquire_task` (SELECT + UPDATE in single `session.begin()`), `WITH RECURSIVE` cycle checks on dependency insertion, Pydantic context validation (8KB limit), state transition matrix enforcement, and defect invariants preventing `DONE` if `OPEN` defects exist. All critical operations must emit structured log events. | Flow engine can query active context securely without raw SQL. |
| FR-5 | Zombie Recovery | Flow Engine | Query tasks where `now() - last_heartbeat_at > 15_minutes` and reset to `PENDING`. Increment `attempt_count`. | Dead locks are automatically recycled. |
| FR-6 | Alembic Integration | System | Add `from specweaver.workspace.memory.store import Task, Epic, TaskDependency, StateTransition, Defect` to `alembic/env.py` so models register to `WorkspaceBase.metadata` before autogeneration. Register a `@event.listens_for(engine.sync_engine, "connect")` callback that executes `PRAGMA foreign_keys=ON` on every new async connection. Generate migration. | DB is structurally updated. FK enforcement is guaranteed in async. All memory models are discoverable by Alembic. |
| FR-7 | Cleanup Strategy | System | When a `Task` status transitions to terminal `ARCHIVED`, execute a trigger/update to set `handover_context = NULL`. | Prevents JSON bloat over time while preserving relational history. Data is not lost during `DONE` rejection cycles. |
| FR-8 | Circuit Breaker | System | If `attempt_count > 3` upon Zombie Recovery, auto-transition task to `BLOCKED` and raise a `Defect` with reason `"circuit_breaker: max retries exceeded"`. | Prevents infinite retry loops from burning LLM API credits. |
| FR-9 | Deadlock Propagation | System | When a task becomes `BLOCKED`, dynamically flag all upstream parent tasks as `UPSTREAM_BLOCKED`. When the blocker is resolved and transitions back to `PENDING`, reverse-propagate to clear `UPSTREAM_BLOCKED` on parents. | Prevents silent queue deadlocks and surfaces critical paths to the user. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Concurrency | `database is locked` errors must be mitigated using `AsyncSession`, the CQRS engine, and Optimistic Concurrency Control (`version` column). OCC read-then-write must execute within a single `async with session.begin()` transaction. Retry logic must use exponential backoff with jitter (`sleep(random(0.1, 0.5) * 2^attempt)`). |
| NFR-2 | Architectural Placement | Code MUST reside in `src/specweaver/workspace/memory/store.py`. Must import `Base` from `workspace.store`, not define a new `DeclarativeBase`. |
| NFR-3 | Type Safety | All SQLAlchemy mapped columns must use Mapped[T] strict typing (SQLAlchemy 2.0 style). |
| NFR-4 | Zombie Timeout | Lock heartbeat timeout is strictly 15 minutes. |
| NFR-5 | Context Structure | `handover_context` must be strictly typed JSON, bounded to factual telemetry (files touched, errors hit) to prevent hallucination transfer. |
| NFR-6 | Token Protection | `MemoryRepository` must enforce an 8KB hard limit on `handover_context` writes, truncating stack traces to the last 2000 chars to prevent 400 Payload LLM crashes. |
| NFR-7 | FK Enforcement | Every async SQLite connection must execute `PRAGMA foreign_keys=ON` via a SQLAlchemy engine event listener. Without this, all CASCADE rules are silently ignored. |
| NFR-8 | Observability | Every critical `MemoryRepository` operation must emit structured logs: `WARNING` on OCC retry, `ERROR` on circuit breaker activation, `INFO` on upstream propagation, `DEBUG` on heartbeat pulses. |
| NFR-9 | Query Performance | All hot-path queries (zombie scan, task acquisition, dependency traversal) must use explicit composite indexes. Zero full table scans at 50K+ rows per project. |

## State Transition Matrix

The `MemoryRepository` MUST enforce this matrix. Any transition not explicitly marked ✅ raises `IllegalStateTransitionError`.

| From ↓ \ To → | PENDING | IN_PROGRESS | DONE | BLOCKED | UPSTREAM_BLOCKED | ARCHIVED |
|----------------|---------|-------------|------|---------|-----------------|----------|
| **PENDING** | — | ✅ acquire | ❌ | ✅ circuit breaker | ✅ propagation | ❌ |
| **IN_PROGRESS** | ✅ release/zombie | — | ✅ complete | ✅ agent fails | ❌ | ❌ |
| **DONE** | ❌ | ✅ PR rejection | — | ❌ | ❌ | ✅ cleanup |
| **BLOCKED** | ✅ manual unblock | ❌ | ❌ | — | ❌ | ✅ abandon |
| **UPSTREAM_BLOCKED** | ✅ downstream resolved | ❌ | ❌ | ❌ | — | ✅ abandon |
| **ARCHIVED** | ❌ | ❌ | ❌ | ❌ | ❌ | — |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| SQLAlchemy | >=2.0.0 | `AsyncSession`, `event` | Yes | Natively supported. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Place schema in `workspace/memory/store.py` | Physical project state belongs in `workspace/` according to DDD rules. Option 2 selected. | No |
| AD-2 | Use DAG Junction Table instead of Tree | Allows multiple parent Epics to depend on a single shared Sub-Task, deduplicating LLM agent work. | Yes — approved by User on 2026-05-05 |
| AD-3 | Do not reuse Knowledge Graph | Graph uses `networkx` RAM loading and is semantically designed for code, not issues. | Yes — approved by User on 2026-05-05 |
| AD-4 | Heartbeat Lock Resilience | Essential to prevent zombie tasks when agents reboot and lose UUIDs. | Yes — approved by User on 2026-05-05 |
| AD-5 | Terminal Context Truncation | Set `handover_context = NULL` on `ARCHIVED` (not `DONE`) to prevent endless JSON string bloat without risking data loss on PR rejection. | Yes — approved by User on 2026-05-05 |
| AD-6 | Optimistic Concurrency (OCC) | Added `version` column to `Task` to mathematically prevent dual-acquisition race conditions when 2 agents poll a dead lock simultaneously. | Yes — approved by User on 2026-05-05 |
| AD-7 | Recursive DAG Protection | `MemoryRepository` enforces `WITH RECURSIVE` queries before edge insertion to prevent infinite hallucinated cycles crashing the Flow Engine. | Yes — approved by User on 2026-05-05 |
| AD-8 | Defect State Invariants | Blocks transition to `DONE` if `OPEN` defects exist, preventing orphaned blockers and impossible mathematical states. | Yes — approved by User on 2026-05-05 |
| AD-9 | 3-Strike Circuit Breaker | `attempt_count` column limits automated retries to 3 before forcing `BLOCKED`. Protects against burning thousands of dollars of API credits on impossible tasks. | Yes — approved by User on 2026-05-05 |
| AD-10 | Strict FK Cascades | `ON UPDATE CASCADE` ensures tasks survive CLI project renaming instead of leaving thousands of orphans. | Yes — approved by User on 2026-05-05 |
| AD-11 | Upstream State Propagation | Automatically bubbles `BLOCKED` states to upstream parents as `UPSTREAM_BLOCKED` to prevent silent queue deadlocks. | Yes — approved by User on 2026-05-05 |
| AD-12 | Shared DeclarativeBase | Memory models MUST import `Base` from `workspace.store` — NOT define a new `DeclarativeBase`. Required for FK cross-references and Alembic discovery. | Yes — approved by User on 2026-05-05 |
| AD-13 | Async PRAGMA Enforcement | Register `@event.listens_for(engine.sync_engine, "connect")` to execute `PRAGMA foreign_keys=ON`. Without this, all CASCADE rules are silently ignored by async connections. | Yes — approved by User on 2026-05-05 |
| AD-14 | Transactional OCC with Backoff | OCC SELECT+UPDATE must execute within a single `session.begin()` to prevent NullPool connection split. Retries use exponential backoff with jitter to prevent thundering herd livelock. | Yes — approved by User on 2026-05-05 |
| AD-15 | Formal State Machine | Exhaustive State Transition Matrix enforced at application layer. Illegal transitions raise `IllegalStateTransitionError`. | Yes — approved by User on 2026-05-05 |
| AD-16 | Observability & Audit Trail | `StateTransition.reason` column for queryable audit. Structured logging on all critical paths (OCC retries, circuit breakers, propagation). | Yes — approved by User on 2026-05-05 |
| AD-17 | Explicit Composite Indexes | 5 indexes on hot-path columns prevent full table scans at scale (50K+ tasks). Without them, zombie recovery and task acquisition degrade quadratically. | Yes — approved by User on 2026-05-05 |
| AD-18 | Epic as Grouping Container | Epic has a simple OPEN/CLOSED status, no state machine or heartbeat. Task.epic_id is nullable — tasks can exist independently. Keeps the Epic model lean. | Yes — approved by User on 2026-05-05 |
| AD-19 | Bounded TransitionReason Enum | `StateTransition.reason` is restricted to a 12-value enum, not free-text. Prevents unsearchable audit trails from inconsistent agent-written strings. | Yes — approved by User on 2026-05-05 |
| AD-20 | Explicit Alembic Model Import | `alembic/env.py` must explicitly import all memory models so they register to `WorkspaceBase.metadata`. Without this, autogeneration produces empty migrations. | Yes — approved by User on 2026-05-05 |
| AD-21 | D-INTL-06 Import Path Verification | D-INTL-06 must import from `workspace.memory.store`. Implementing agent must verify against `tach.toml` that `intelligence → workspace` is an allowed dependency direction. | Yes — approved by User on 2026-05-05 |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Agent Memory State Tracking | How to use `MemoryRepository` to acquire tasks, pulse heartbeats, and handle OCC retries. | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: SQLAlchemy Schema & Alembic Definitions
- **Scope**: Define the strict OCC/Cascade SQLAlchemy entity classes (Task with all columns/indexes, Epic with OPEN/CLOSED status, TaskDependency with indexed FKs, StateTransition with bounded `TransitionReason` enum, Defect) reusing `Base` from `workspace.store`. Register PRAGMA event listener. Add explicit model imports to `alembic/env.py`. Generate the DB migration.
- **FRs**: [FR-1, FR-2, FR-3, FR-6]
- **Inputs**: `specweaver/workspace/store.py` Base class (import, do not redefine).
- **Outputs**: `src/specweaver/workspace/memory/store.py` (Models + PRAGMA listener + indexes + TransitionReason enum) + updated `alembic/env.py` + `alembic/versions/` migration script.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_sf1_implementation_plan.md

### SF-2: Core CRUD & State Machine
- **Scope**: Implement the foundational `MemoryRepository` with basic CRUD operations, the formal State Transition Matrix enforcement, defect invariants (no `DONE` with `OPEN` defects), and context cleanup on `ARCHIVED`.
- **FRs**: [FR-4 (core CRUD + state matrix + defect invariants), FR-7]
- **Inputs**: The SQLAlchemy models defined in SF-1.
- **Outputs**: `MemoryRepository` class with `create_task`, `get_task`, `list_tasks`, `transition_state` (matrix enforcement + defect invariants), `update_handover_context` (basic), `mark_archived` (context truncation). Structured logging on state transitions.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_sf2_implementation_plan.md

### SF-3: DAG & Context Validation
- **Scope**: Implement dependency graph management with `WITH RECURSIVE` cycle detection, transactional OCC `acquire_task` with exponential backoff + jitter, and Pydantic `HandoverContext` validation with 8KB truncation.
- **FRs**: [FR-4 (DAG cycle checks + OCC acquire + Pydantic context validation)]
- **Inputs**: The `MemoryRepository` core CRUD from SF-2.
- **Outputs**: `insert_dependency` (WITH RECURSIVE cycle check), `acquire_task` (transactional OCC + backoff), `update_handover_context` (Pydantic 8KB validation + truncation).
- **Depends on**: SF-2
- **Impl Plan**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_sf3_implementation_plan.md

### SF-4: Resilience & Recovery
- **Scope**: Implement Zombie Recovery with heartbeat scanning, 3-Strike Circuit Breaker, and upstream `BLOCKED` → `UPSTREAM_BLOCKED` DAG propagation with reverse-clear on unblock.
- **FRs**: [FR-5, FR-8, FR-9]
- **Inputs**: The `MemoryRepository` core CRUD and state machine from SF-2.
- **Outputs**: `recycle_zombies` (heartbeat scan + attempt_count increment), `circuit_breaker` (auto-BLOCKED + Defect creation), `propagate_blocked` (upstream cascade), `clear_upstream_blocked` (reverse cascade). Structured logging on all resilience events.
- **Depends on**: SF-2
- **Impl Plan**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_sf4_implementation_plan.md

## Execution Order

1. SF-1 (Schema & DB Migration) — start immediately.
2. SF-2 (Core CRUD & State Machine) — depends on SF-1.
3. SF-3 and SF-4 **in parallel** — both depend only on SF-2.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | SQLAlchemy Schema & Alembic Definitions | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Core CRUD & State Machine | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-3 | DAG & Context Validation | SF-2 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-4 | Resilience & Recovery | SF-2 | ✅ | ✅ | ✅ | ✅ | ⬜ |

## Session Handoff

**Current status**: SF-2 Implementation Plan is APPROVED.
**Next step**: Run `/dev docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_sf2_implementation_plan.md` to begin TDD development.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
