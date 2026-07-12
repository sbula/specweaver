# Implementation Plan: Agent Memory Bank [SF-02: Core CRUD & State Machine]

> [!NOTE]
> **Status:** 🟢 Completed
> **Execution Date:** 2026-05-06
> All components successfully implemented, fully typed, and verified via TDD (62 unit tests) and 10 integration/e2e simulation tests. Pre-commit quality gates passed.

- **Feature ID**: B-INTL-09
- **Sub-Feature**: SF-02 — Core CRUD & State Machine
- **Design Document**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_sf02_implementation_plan.md
- **Status**: APPROVED

---

## Scope Summary

SF-02 implements the foundational `MemoryRepository` class providing core CRUD operations and formal State Transition Matrix enforcement for the Agent Memory Bank. It covers:

- **1 new class**: `MemoryRepository` in `src/specweaver/workspace/memory/repository.py` (16 public methods)
- **2 custom exceptions**: `IllegalStateTransitionError`, `DefectBlocksCompletionError` in `src/specweaver/workspace/memory/errors.py`
- **Core CRUD methods**: `create_task`, `create_epic`, `get_task`, `get_epic`, `list_tasks`, `list_epics`, `update_task`, `create_defect`, `resolve_defect`, `list_defects`, `update_handover_context`, `add_task_dependency`, `remove_task_dependency`
- **State machine enforcement**: `transition_state` (matrix validation + audit trail + defect invariants)
- **Epic lifecycle**: `close_epic` (dedicated, per AD-18 — no state machine)
- **Audit trail**: `get_task_transitions`
- **Context cleanup**: `handover_context = NULL` on transition to `ARCHIVED` (FR-7)
- **Structured logging**: On all critical operations (NFR-8)
- **Input validation**: `_validate_non_empty()` helper for title fields

**FRs covered**: FR-4 (core CRUD + state matrix + defect invariants), FR-7 (cleanup on ARCHIVED).

**FRs explicitly NOT covered (deferred to SF-03 / SF-04)**:
- OCC `acquire_task` with backoff → SF-03
- `WITH RECURSIVE` cycle checks → SF-03
- Pydantic context validation (8KB) → SF-03
- Zombie recovery, circuit breaker, upstream propagation → SF-04

**Inputs**: SQLAlchemy models from SF-01 (`Task`, `Epic`, `TaskDependency`, `StateTransition`, `Defect`, `ALLOWED_TRANSITIONS`, all enums).

**Outputs**:
- `src/specweaver/workspace/memory/repository.py` (new — `MemoryRepository` class, 16 methods)
- `src/specweaver/workspace/memory/errors.py` (new — `IllegalStateTransitionError`, `DefectBlocksCompletionError`)
- `tests/unit/workspace/test_memory_repository.py` (new — 55 repository-level tests)

---

## Research Notes

### Codebase Pattern Analysis

1. **Repository Pattern**: The codebase uses a consistent pattern across all domain stores. Each repository takes an `AsyncSession` as its constructor argument and uses `await self.session.flush()` (not `commit()`) to push changes within a caller-managed transaction boundary. See:
   - `WorkspaceRepository.__init__(self, session: AsyncSession)` in `workspace/store.py:73`
   - `FlowRepository.__init__(self, session: AsyncSession)` in `core/flow/store.py:29`

2. **Session Lifecycle**: The `session_scope()` context manager in `database.py:176-192` handles commit/rollback. Repositories do NOT call `session.commit()` directly — they call `session.flush()`. The `session_scope()` caller commits at the end.

3. **Return Format**: `WorkspaceRepository` returns `dict[str, object]` from `get_*` and `list_*` methods rather than ORM model instances. `FlowRepository` also uses this pattern. **SF-02 MUST follow this pattern** to maintain consistency.

4. **Logging Convention**: The codebase uses `logger = logging.getLogger(__name__)` with `%s` lazy formatting (Pattern #20 in `special_patterns_and_adaptations.md`). All critical events use appropriate severity levels.

5. **PRAGMA Integration**: SF-01 created `register_fk_pragma_listener()` in `database.py`. The repository itself does NOT need to call this — it is the session creator's responsibility (either `session_scope()` or test fixtures).

6. **No `__init__.py`**: The project is a PEP 420 Implicit Namespace Package. No `__init__.py` files should be created.

7. **`tach.toml` Boundary**: `src.specweaver.workspace` is registered as a module with `depends_on = []`. The new `memory/repository.py` file falls under this existing boundary and only imports from `workspace.memory.store` (same boundary) and `core.config.database` (allowed by `workspace/context.yaml`).

### SQLAlchemy Async Patterns (External Research)

1. **OCC with `version_id_col`**: SQLAlchemy 2.0 natively supports OCC via `__mapper_args__ = {"version_id_col": version}`. However, this auto-increments `version` on **every flush**, not just on specific state transitions. Since SF-02's scope is basic CRUD + state machine (without OCC acquisition), we will NOT use `version_id_col` mapper args in SF-02. We will manually manage the `version` column. SF-03 will implement the transactional OCC `acquire_task` with explicit version checking and `StaleDataError`-style retry logic.

2. **`select()` + `session.get()`**: For single-entity lookups by PK, `session.get(Model, pk)` is the correct async pattern (uses identity map). For filtered queries, use `select(Model).where(...)`.

3. **`session.flush()` vs `session.commit()`**: `flush()` pushes changes to the DB within the current transaction without committing. This is the correct pattern when the repository is embedded within a larger transactional scope managed by `session_scope()`.

---

## HITL Decisions Resolved (Phase 4)

All 10 findings from the Phase 2/3 audit were reviewed and approved by HITL on 2026-05-06.

| # | Finding | Severity | Decision |
|---|---------|----------|----------|
| 1 | File placement: `repository.py` vs `store.py` | HIGH | **Separate `repository.py`** — MemoryRepository is too complex (13+ methods, grows in SF-03/SF-04) to coexist with schema. |
| 2 | Exception placement: `errors.py` vs inline | MEDIUM | **Separate `errors.py`** — enables clean imports by downstream consumers (D-INTL-06). |
| 3 | Return type: dict vs Pydantic/TypedDict | HIGH | **`dict[str, object]`** — matches existing `WorkspaceRepository` and `FlowRepository` convention. |
| 4 | FK validation: pre-validate vs catch IntegrityError | HIGH | **Pre-validate with SELECT** — matches existing pattern. **Must be documented** as an explicit DB-portability concern. |
| 5 | Transaction scope: single flush vs SAVEPOINT | HIGH | **Single `flush()`** — trusts `session_scope()` for transaction boundary, matches existing pattern. |
| 6 | Pagination: yes vs no | MEDIUM | **No pagination** — matches existing pattern. **Must be documented** in the MVP Decision Register. |
| 7 | Epic close: dedicated vs generic | LOW | **Dedicated `close_epic()`** — AD-18 explicitly says no state machine for Epic. |
| 8 | tach.toml: explicit vs inherited | MEDIUM | **Inherited** — verify during `/pre-commit`. |
| 9 | Documentation updates | MEDIUM | Listed: testing_guide, design doc progress tracker. |
| 10 | Architecture verification | ✅ PASS | No violations found. |

> [!WARNING]
> **HITL Action Item (Finding #1)**: User approved but flagged that `FlowRepository` coexisting with its schema in `core/flow/store.py` should be refactored to follow the same separation pattern. **Tech Debt: TECH-006** added to Backlog.

> [!WARNING]
> **HITL Action Item (Finding #4)**: The pre-validation pattern (SELECT before INSERT to produce clean `ValueError` instead of opaque `IntegrityError`) MUST be documented in `docs/dev_guides/special_patterns_and_adaptations.md` during `/pre-commit` Phase 6. This is a DB-portability concern: if SpecWeaver ever migrates from SQLite to PostgreSQL, this pattern may need revisiting since Postgres provides richer error codes.

> [!WARNING]
> **HITL Action Item (Finding #6)**: User requested an **MVP Decision Register** — a living document that explicitly tracks design decisions that are acceptable for MVP but may need changing for production scale. To be created as `docs/roadmap/mvp_decision_register.md` during `/pre-commit` Phase 6. First entries: no pagination on `list_*` methods, pre-validation SELECT pattern.

---

## Red Team / Blue Team Findings (Merged)

The following 8 findings from the adversarial audit have been accepted and merged into this plan:

| RT | Finding | Resolution |
|----|---------|------------|
| RT-1 | Defensive guard against unknown `TaskStatus` in `ALLOWED_TRANSITIONS` | Added guard: `if task.status not in ALLOWED_TRANSITIONS` → `IllegalStateTransitionError` |
| RT-2 | Defect invariant check is non-atomic (theoretical race window) | Documented as known gap; closed by SF-03 OCC |
| RT-3 | Empty/whitespace `title` passes `nullable=False` | Added `_validate_non_empty()` helper + tests |
| RT-4 | `update_task` / `update_handover_context` must explicitly set `updated_at` | Made explicit in all mutation methods |
| RT-5 | `uuid.UUID` objects in return dicts crash `json.dumps()` | Convert to `str()` in `_to_dict` helpers |
| RT-6 | `list_*` returns `[]` for nonexistent projects (undocumented) | Documented as convention + added test |
| RT-8 | `list_epics` / `list_tasks` ordering not tested | Added ordering tests |
| RT-10 | Defect create/resolve missing structured logging (NFR-8) | Added logging + tests |
| RT-13 | Cross-Entity Integrity (Project Hijacking) | Validate `epic.project_name == task.project_name` in `create_task` |
| RT-14 | Validation Bypass in `update_task` | Added `_validate_non_empty` to `update_task` |
| RT-15 | Missing Dependency Management (DAG CRUD) | Added `add_task_dependency` and `remove_task_dependency` |
| RT-16 | Enum Serialization Crash in Audit Trail | Enforced `.value` for all Enums in `_to_dict` helpers |
| RT-17 | Reason semantics validation | Documented that semantic validation belongs in Flow layer |
| RT-18 | Hard Deletion vs Soft Deletion | Documented that omission of DELETE is an intentional forensic design choice |
| RT-19 | `created_at`/`updated_at` have no `default=` on model columns | Mandated explicit `datetime.now(UTC)` init in all `create_*` methods |
| RT-20 | Duplicate dependency link → unhandled `IntegrityError` | Pre-check + `ValueError("Dependency already exists")` |
| RT-22 | Scope Summary stale after amendments | Updated scope to reflect 16 methods, 2 exceptions, 55 tests |
| RT-23 | `close_epic` missing from `updated_at` rule | Added `close_epic` to explicit timestamp rule |
| RT-25 | RT-13 test needs second project in fixture | Documented inline setup for cross-project test |

---

## Proposed Changes

### Component 1: Custom Exceptions (`workspace/memory/`)

#### [NEW] errors.py — `src/specweaver/workspace/memory/errors.py`

**Purpose**: Define domain-specific exceptions for the Memory Bank.

```python
"""Agent Memory Bank — custom exceptions."""


class IllegalStateTransitionError(Exception):
    """Raised when a task state transition violates the allowed matrix (AD-15).

    Attributes:
        task_id: The UUID of the task.
        from_status: The current status of the task.
        to_status: The requested target status.
    """

    def __init__(self, task_id, from_status, to_status):
        self.task_id = task_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Illegal state transition for task {task_id}: "
            f"{from_status.value} → {to_status.value}"
        )


class DefectBlocksCompletionError(Exception):
    """Raised when a task cannot transition to DONE due to OPEN defects (AD-8).

    Attributes:
        task_id: The UUID of the task.
        open_defect_count: Number of OPEN defects blocking the transition.
    """

    def __init__(self, task_id, open_defect_count):
        self.task_id = task_id
        self.open_defect_count = open_defect_count
        super().__init__(
            f"Cannot complete task {task_id}: "
            f"{open_defect_count} OPEN defect(s) must be resolved first"
        )
```

---

### Component 2: Memory Repository (`workspace/memory/`)

#### [NEW] repository.py — `src/specweaver/workspace/memory/repository.py`

**Purpose**: Implement `MemoryRepository` with core CRUD, state machine enforcement, defect invariants, and context cleanup.

**Input validation helper** (RT-3):
```python
def _validate_non_empty(field_name: str, value: str) -> None:
    """Raise ValueError if value is empty or whitespace-only."""
    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be empty or whitespace-only")
```

**Constructor pattern** (follows `WorkspaceRepository` and `FlowRepository`):
```python
class MemoryRepository:
    """Repository for the Agent Memory Bank (US-28).

    Provides core CRUD operations, formal State Transition Matrix enforcement,
    defect invariants, and context cleanup for task lifecycle management.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
```

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_epic` | `(project_name: str, title: str, description: str \| None = None) → dict[str, object]` | Create a new Epic. Validates project exists. Returns dict. |
| `get_epic` | `(epic_id: uuid.UUID) → dict[str, object] \| None` | Fetch epic by PK. Returns None if not found. |
| `list_epics` | `(project_name: str) → list[dict[str, object]]` | List all epics for a project, ordered by created_at desc. |
| `close_epic` | `(epic_id: uuid.UUID) → dict[str, object]` | Set epic status to CLOSED. Raises ValueError if not found or already CLOSED. |
| `create_task` | `(project_name: str, title: str, description: str \| None = None, epic_id: uuid.UUID \| None = None) → dict[str, object]` | Create a new Task with status=PENDING, version=1, attempt_count=0. Validates project and epic (if provided) exist. |
| `get_task` | `(task_id: uuid.UUID) → dict[str, object] \| None` | Fetch task by PK. Returns None if not found. |
| `list_tasks` | `(project_name: str, *, status: TaskStatus \| None = None) → list[dict[str, object]]` | List tasks for a project, optionally filtered by status. Ordered by created_at desc. |
| `update_task` | `(task_id: uuid.UUID, *, title: str \| None = None, description: str \| None = None) → dict[str, object]` | Update mutable task fields. Raises ValueError if not found. |
| `transition_state` | `(task_id: uuid.UUID, to_status: TaskStatus, reason: TransitionReason, *, worker_id: str \| None = None) → dict[str, object]` | Enforce state transition matrix (AD-15). Check defect invariants (AD-8). Record audit trail. Set `handover_context = NULL` on ARCHIVED (FR-7, AD-5). Raises `IllegalStateTransitionError` or `DefectBlocksCompletionError`. |
| `create_defect` | `(task_id: uuid.UUID, title: str, description: str \| None = None) → dict[str, object]` | Create OPEN defect linked to task. Validates task exists. |
| `resolve_defect` | `(defect_id: int) → dict[str, object]` | Set defect status to RESOLVED with `resolved_at` timestamp. Raises ValueError if not found or already resolved. |
| `list_defects` | `(task_id: uuid.UUID, *, status: DefectStatus \| None = None) → list[dict[str, object]]` | List defects for a task, optionally filtered by status. |
| `get_task_transitions` | `(task_id: uuid.UUID) → list[dict[str, object]]` | Get full audit trail for a task, ordered by timestamp asc. |
| `update_handover_context` | `(task_id: uuid.UUID, context: str \| None) → dict[str, object]` | Basic context update (no Pydantic validation — that's SF-03). Validates task exists. |
| `add_task_dependency` | `(parent_id: uuid.UUID, child_id: uuid.UUID) → None` | Add DAG link (RT-15). Validates both tasks exist. Raises ValueError on self-dependency or duplicate link (RT-20). Cycle checks deferred to SF-03. |
| `remove_task_dependency` | `(parent_id: uuid.UUID, child_id: uuid.UUID) → None` | Remove DAG link (RT-15). Raises ValueError if tasks or link not found. |

> [!IMPORTANT]
> **`transition_state` Implementation Detail (Critical)**:
> The method MUST:
> 1. Fetch the task by ID (raise ValueError if not found).
> 2. **Defensive guard (RT-1)**: If `task.status not in ALLOWED_TRANSITIONS`, raise `IllegalStateTransitionError`. This prevents `KeyError` crashes if a future enum value is added without updating the matrix.
> 3. Check `ALLOWED_TRANSITIONS[current_status]` for `to_status` — raise `IllegalStateTransitionError` if not allowed.
> 4. If `to_status == DONE`: query `Defect` table for any `status == OPEN` with this `task_id`. If count > 0, raise `DefectBlocksCompletionError` (AD-8).
> 5. Update `task.status`, `task.updated_at = datetime.now(UTC)` **(RT-4: explicit timestamp).**
> 6. If `to_status == ARCHIVED`: set `task.handover_context = None` (FR-7, AD-5).
> 7. Insert `StateTransition` record with `from_status`, `to_status`, `reason`, `worker_id`, `timestamp`.
> 8. Emit structured log: `INFO` for normal transitions, `WARNING` for BLOCKED transitions.
> 9. `flush()`.
> 10. Return the updated task as dict.

> [!NOTE]
> **RT-2: Defect invariant race condition**: The defect check (step 4) and status update (step 5) are non-atomic within the same `flush()`. This is a theoretical gap that is practically mitigated by SQLite's WAL write serialization and `NullPool` connection isolation. SF-03's transactional OCC will close this gap for true multi-process concurrent access.

> [!CAUTION]
> **RT-19: Explicit Timestamp Initialization Rule**: The `Task`, `Epic`, and `Defect` models have NO `default=` on `created_at` or `updated_at` columns. All `create_*` methods MUST explicitly set `created_at = datetime.now(UTC)` (and `updated_at` for Task/Epic) at creation time. `StateTransition.timestamp` must also be explicitly set. Failing to do this will crash with `IntegrityError: NOT NULL constraint failed`. This follows the pattern established in `WorkspaceRepository.register_project()` (store.py:82).

> [!IMPORTANT]
> **RT-4 & RT-23: Explicit `updated_at` Rule**: Every mutation method (`update_task`, `transition_state`, `update_handover_context`, `close_epic`) MUST explicitly set `entity.updated_at = datetime.now(UTC)` before calling `flush()`. SQLAlchemy does NOT auto-update timestamps — there is no `onupdate` hook on the column.

> [!IMPORTANT]
> **RT-13: Cross-Entity Integrity Rule**: `create_task` MUST verify that if an `epic_id` is provided, the associated Epic has the exact same `project_name` as the new task. If not, raise `ValueError("Epic belongs to a different project")`.

> [!IMPORTANT]
> **RT-3 & RT-14: Title Validation Rule**: `create_task`, `create_epic`, `create_defect`, and `update_task` (if title is not None) MUST call `_validate_non_empty("title", title)` before mutating the entity. SQLAlchemy `nullable=False` does NOT reject empty strings.

> [!IMPORTANT]
> **RT-10: Defect Logging Rule (NFR-8)**: `create_defect` MUST emit `logger.info("Defect created: task_id=%s, defect_id=%s, title=%s", ...)`. `resolve_defect` MUST emit `logger.info("Defect resolved: defect_id=%s, task_id=%s", ...)`.

> [!NOTE]
> **RT-17 & RT-18: Architectural Boundaries**: The repository intentionally lacks semantic validation for `TransitionReason` (this belongs in the Flow orchestrator) and intentionally lacks `delete_*` methods (hard deletion destroys the forensic audit trail, use `ARCHIVED`/`RESOLVED` states instead).

> [!NOTE]
> **`version` Column Handling in SF-02**: SF-02 does NOT increment `task.version` during state transitions. The `version` column is reserved for Optimistic Concurrency Control in SF-03's `acquire_task`. SF-02 sets `version=1` on creation and leaves it unchanged. SF-03 will use it to prevent dual-acquisition race conditions.

> [!NOTE]
> **`attempt_count` Column Handling in SF-02**: SF-02 does NOT modify `attempt_count`. It is set to `0` on creation and managed exclusively by SF-04's zombie recovery and circuit breaker logic.

**Serialization helper** (private method, DRY for all return dicts — **RT-5: UUIDs converted to `str()`**):

```python
@staticmethod
def _task_to_dict(task: Task) -> dict[str, object]:
    return {
        "id": str(task.id),  # RT-5: UUID → str for JSON serialization safety
        "project_name": task.project_name,
        "epic_id": str(task.epic_id) if task.epic_id else None,  # RT-5
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "assigned_worker_id": task.assigned_worker_id,
        "locked_at": task.locked_at.isoformat() if task.locked_at else None,
        "last_heartbeat_at": task.last_heartbeat_at.isoformat() if task.last_heartbeat_at else None,
        "handover_context": task.handover_context,
        "version": task.version,
        "attempt_count": task.attempt_count,
        "created_at": task.created_at.isoformat() if isinstance(task.created_at, datetime) else task.created_at,
        "updated_at": task.updated_at.isoformat() if isinstance(task.updated_at, datetime) else task.updated_at,
    }
```

Similar `_epic_to_dict`, `_defect_to_dict`, `_transition_to_dict` helpers. All UUID fields MUST use `str()` conversion (RT-5). All Enum fields (like `transition.from_status`, `transition.reason`) MUST use `.value` conversion to prevent `json.dumps()` crashes (RT-16).

> [!NOTE]
> **RT-6: `list_*` Convention**: `list_tasks` and `list_epics` return an empty list `[]` for nonexistent project names. They do NOT raise `ValueError`. This matches `WorkspaceRepository.get_standards()` and is the established convention for list operations. Callers should check project existence separately if needed.

---

### Component 3: Tests

#### [NEW] test_memory_repository.py — `tests/unit/workspace/test_memory_repository.py`

**Test fixture strategy**: Reuse the same `engine`/`session`/`base_project` fixture pattern from `test_memory_store.py` (SF-01). The test file will use `@pytest.mark.asyncio` class-based grouping.

> [!NOTE]
> **RT-25: Second Project for Cross-Entity Tests**: `test_create_task_epic_project_mismatch` (test #5) requires an Epic from a different project. This test must create a second project inline within the test body (not via a shared fixture) to keep the fixture simple.

| # | Test | Category | What it verifies |
|---|------|----------|-----------------|
| 1 | `test_create_task_happy_path` | Happy Path | Task creation returns dict with correct defaults (PENDING, version=1, attempt_count=0). UUIDs are strings (RT-5). |
| 2 | `test_create_task_invalid_project` | Boundary | Raises ValueError for nonexistent project |
| 3 | `test_create_task_with_epic` | Happy Path | Task linked to existing epic |
| 4 | `test_create_task_invalid_epic` | Boundary | Raises ValueError for nonexistent epic_id |
| 5 | `test_create_task_epic_project_mismatch` | RT-13 | Raises ValueError if epic belongs to different project |
| 6 | `test_create_task_empty_title` | RT-3 | Raises ValueError for empty/whitespace title |
| 7 | `test_get_task_found` | Happy Path | Returns task dict by UUID |
| 8 | `test_get_task_not_found` | Boundary | Returns None for unknown UUID |
| 9 | `test_list_tasks_all` | Happy Path | Lists all tasks for a project |
| 10 | `test_list_tasks_filtered_by_status` | Happy Path | Filters by TaskStatus |
| 11 | `test_list_tasks_empty_project` | Boundary | Returns empty list for project with no tasks |
| 12 | `test_list_tasks_nonexistent_project` | RT-6 | Returns empty list for nonexistent project |
| 13 | `test_list_tasks_ordering` | RT-8 | Creates 2+ tasks, verifies created_at desc ordering |
| 14 | `test_update_task` | Happy Path | Updates title/description, bumps updated_at (RT-4) |
| 15 | `test_update_task_empty_title` | RT-14 | Raises ValueError for empty/whitespace title |
| 16 | `test_update_task_not_found` | Boundary | Raises ValueError |
| 17 | `test_transition_state_happy_path` | Happy Path | PENDING → IN_PROGRESS succeeds, audit trail created |
| 18 | `test_transition_state_illegal` | Boundary | PENDING → DONE raises IllegalStateTransitionError |
| 19 | `test_transition_state_from_archived` | Boundary | ARCHIVED → anything raises IllegalStateTransitionError |
| 20 | `test_transition_done_blocked_by_defect` | Invariant | IN_PROGRESS → DONE with OPEN defects raises DefectBlocksCompletionError |
| 21 | `test_transition_done_with_resolved_defects` | Invariant | IN_PROGRESS → DONE with all RESOLVED defects succeeds |
| 22 | `test_transition_archived_clears_context` | FR-7 | Transition to ARCHIVED sets handover_context = None |
| 23 | `test_transition_state_audit_trail` | Audit | StateTransition record has correct from/to/reason/worker_id |
| 24 | `test_transition_updates_timestamp` | RT-4 | Verifies `updated_at` is bumped on state transition |
| 25 | `test_create_epic_happy_path` | Happy Path | Epic creation returns dict with status=OPEN |
| 26 | `test_create_epic_invalid_project` | Boundary | Raises ValueError for nonexistent project |
| 27 | `test_create_epic_empty_title` | RT-3 | Raises ValueError for empty/whitespace title |
| 28 | `test_list_epics_ordering` | RT-8 | Creates 2+ epics, verifies created_at desc ordering |
| 29 | `test_close_epic` | Happy Path | OPEN → CLOSED succeeds |
| 30 | `test_close_epic_already_closed` | Boundary | Raises ValueError |
| 31 | `test_close_epic_not_found` | Boundary | Raises ValueError |
| 32 | `test_close_epic_updates_timestamp` | RT-23 | Verifies `updated_at` is bumped on close |
| 33 | `test_create_defect_happy_path` | Happy Path | Defect created with status=OPEN |
| 34 | `test_create_defect_invalid_task` | Boundary | Raises ValueError for nonexistent task |
| 35 | `test_create_defect_empty_title` | RT-3 | Raises ValueError for empty/whitespace title |
| 36 | `test_resolve_defect` | Happy Path | OPEN → RESOLVED, resolved_at set |
| 37 | `test_resolve_defect_already_resolved` | Boundary | Raises ValueError |
| 38 | `test_resolve_defect_not_found` | Boundary | Raises ValueError |
| 39 | `test_list_defects` | Happy Path | Lists defects for a task |
| 40 | `test_list_defects_filtered` | Happy Path | Filters by DefectStatus |
| 41 | `test_get_task_transitions` | Happy Path | Returns audit trail ordered by timestamp |
| 42 | `test_update_handover_context` | Happy Path | Sets/clears handover_context on task |
| 43 | `test_update_handover_context_task_not_found` | Boundary | Raises ValueError |
| 44 | `test_update_handover_context_updates_timestamp` | RT-4 | Verifies `updated_at` is bumped |
| 45 | `test_add_task_dependency_happy_path` | Happy Path | Successfully creates TaskDependency link (RT-15) |
| 46 | `test_add_task_dependency_self_loop` | Boundary | Raises ValueError when parent_id == child_id (RT-15) |
| 47 | `test_add_task_dependency_duplicate` | RT-20 | Raises ValueError when link already exists |
| 48 | `test_remove_task_dependency` | Happy Path | Successfully removes TaskDependency link (RT-15) |
| 49 | `test_transition_all_valid_paths` | Matrix | Exhaustively tests every ✅ cell in the State Transition Matrix |
| 50 | `test_transition_all_invalid_paths` | Matrix | Exhaustively tests every ❌ cell in the State Transition Matrix |
| 51 | `test_structured_logging_on_transition` | NFR-8 | Verifies logger.info emitted on state transition (using caplog) |
| 52 | `test_structured_logging_on_blocked` | NFR-8 | Verifies logger.warning emitted on BLOCKED transition |
| 53 | `test_structured_logging_on_defect_create` | RT-10 | Verifies logger.info emitted on defect creation |
| 54 | `test_structured_logging_on_defect_resolve` | RT-10 | Verifies logger.info emitted on defect resolution |
| 55 | `test_create_task_sets_timestamps` | RT-19 | Verifies `created_at` and `updated_at` are set on creation |

> [!IMPORTANT]
> **Exhaustive Matrix Tests (49 & 50)**: These tests parametrize over ALL 30 cells (6×5 excluding diagonal) of the State Transition Matrix. For each `(from, to)` pair, they verify either success or `IllegalStateTransitionError`. This mathematically proves the state machine is airtight.

---

## Verification Plan

### Automated Tests
```bash
pytest tests/unit/workspace/test_memory_repository.py -v
pytest tests/unit/workspace/test_memory_store.py -v    # regression check
tach check
mypy src/specweaver/workspace/memory/repository.py src/specweaver/workspace/memory/errors.py --ignore-missing-imports
ruff check src/specweaver/workspace/memory/
```

### Manual Verification
- Confirm that `tach check` passes without requiring `tach.toml` changes (new files fall under existing `src.specweaver.workspace` boundary).
- Verify full test suite regression: `pytest` (all 4554+ tests pass).

---

## Backlog / Deferred Items

1. **OCC `acquire_task` with version column** → Deferred to SF-03. SF-02 does not increment `version`.
2. **Pydantic `HandoverContext` validation** → Deferred to SF-03. SF-02 does basic string storage only.
3. **`WITH RECURSIVE` cycle detection on dependency insert** → Deferred to SF-03.
4. **Zombie recovery + circuit breaker + upstream propagation** → Deferred to SF-04.
5. **`tach.toml` registration for `workspace.memory`** → Only if `tach check` requires it. Currently `workspace` covers it.
6. **TECH-006: FlowRepository separation** → Refactor `core/flow/store.py` to separate `FlowRepository` into its own `core/flow/repository.py`, matching the `workspace/memory/` separation pattern. Low priority, no functional impact.
7. **MVP Decision Register** → Create `docs/roadmap/mvp_decision_register.md` during `/pre-commit` to track MVP-acceptable decisions that should be revisited for production.
8. **Pre-validation pattern documentation** → Document the SELECT-before-INSERT pattern in `docs/dev_guides/special_patterns_and_adaptations.md` as a DB-portability concern.
