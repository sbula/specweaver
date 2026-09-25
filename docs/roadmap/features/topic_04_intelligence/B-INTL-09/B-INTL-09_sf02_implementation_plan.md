# B-INTL-09 SF-02 — Core CRUD & State Machine

**Status**: APPROVED — HITL decisions approved on 2026-05-06. 🟢 Completed 2026-05-06. ·
**FRs owned**: FR-4 (core CRUD + state matrix + defect invariants), FR-7 (cleanup on ARCHIVED) ·
**Depends on**: SF-01 · Design: [B-INTL-09_design.md](B-INTL-09_design.md) §Sub-features → SF-02

## Goal

The foundational `MemoryRepository`: core CRUD and formal State Transition Matrix enforcement.

- **1 new class**: `MemoryRepository` in `src/specweaver/workspace/memory/repository.py` (16 public methods)
- **2 custom exceptions**: `IllegalStateTransitionError`, `DefectBlocksCompletionError` in `src/specweaver/workspace/memory/errors.py`
- **Core CRUD**: `create_task`, `create_epic`, `get_task`, `get_epic`, `list_tasks`,
  `list_epics`, `update_task`, `create_defect`, `resolve_defect`, `list_defects`,
  `update_handover_context`, `add_task_dependency`, `remove_task_dependency`
- **State machine**: `transition_state` (matrix validation + audit trail + defect invariants)
- **Epic lifecycle**: `close_epic` (dedicated, per AD-18 — no state machine)
- **Audit trail**: `get_task_transitions`
- **Context cleanup**: `handover_context = NULL` on transition to `ARCHIVED` (FR-7)
- **Structured logging** on all critical operations (NFR-8)
- **Input validation**: `_validate_non_empty()` helper for title fields

Not here: OCC `acquire_task` with backoff, `WITH RECURSIVE` cycle checks, Pydantic context
validation (8KB) → SF-03. Zombie recovery, circuit breaker, upstream propagation → SF-04.

## Where it plugs in

Inputs: the SF-01 models (`Task`, `Epic`, `TaskDependency`, `StateTransition`, `Defect`,
`ALLOWED_TRANSITIONS`, all enums).

| Fact | Where |
|---|---|
| Every repository takes an `AsyncSession` in its constructor and uses `await self.session.flush()` (not `commit()`) inside a caller-managed transaction. | `WorkspaceRepository.__init__(self, session: AsyncSession)` in `workspace/store.py:73`; `FlowRepository.__init__(self, session: AsyncSession)` in `core/flow/store.py:29` |
| `session_scope()` handles commit/rollback; repositories only flush, the `session_scope()` caller commits. | `database.py:176-192` |
| `WorkspaceRepository` and `FlowRepository` return `dict[str, object]` from `get_*` and `list_*`, not ORM instances. **SF-02 MUST follow this pattern.** | — |
| Logging: `logger = logging.getLogger(__name__)` with `%s` lazy formatting (Pattern #20 in `special_patterns_and_adaptations.md`). | — |
| SF-01's `register_fk_pragma_listener()` is the session creator's job (`session_scope()` or test fixtures), not the repository's. | `database.py` |
| PEP 420 Implicit Namespace Package: no `__init__.py` files. | — |
| `src.specweaver.workspace` is a `tach.toml` module with `depends_on = []`. `memory/repository.py` falls under it and imports only `workspace.memory.store` (same boundary) and `core.config.database` (allowed by `workspace/context.yaml`). | `tach.toml` |

SQLAlchemy async notes:

- **No `version_id_col`.** SQLAlchemy 2.0's `__mapper_args__ = {"version_id_col": version}` bumps
  `version` on **every flush**, not only on specific transitions. SF-02 manages `version` manually;
  SF-03's transactional OCC `acquire_task` checks it explicitly with `StaleDataError`-style retry.
- **`select()` + `session.get()`**: `session.get(Model, pk)` for PK lookups (uses the identity map); `select(Model).where(...)` for
  filtered queries.
- `flush()` pushes changes inside the current transaction without committing — right when the
  repository is embedded in a `session_scope()`.

## Changes

1. **Exceptions** · `src/specweaver/workspace/memory/errors.py` (new):

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

2. **`MemoryRepository`** · `src/specweaver/workspace/memory/repository.py` (new) — core CRUD, state
   machine, defect invariants, context cleanup.

Input validation helper (RT-3):
```python
def _validate_non_empty(field_name: str, value: str) -> None:
    """Raise ValueError if value is empty or whitespace-only."""
    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be empty or whitespace-only")
```

Constructor (follows `WorkspaceRepository` and `FlowRepository`):
```python
class MemoryRepository:
    """Repository for the Agent Memory Bank (US-28).

    Provides core CRUD operations, formal State Transition Matrix enforcement,
    defect invariants, and context cleanup for task lifecycle management.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
```

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

**`transition_state` MUST:**

1. Fetch the task by ID (raise ValueError if not found).
2. **Defensive guard (RT-1)**: if `task.status not in ALLOWED_TRANSITIONS`, raise
   `IllegalStateTransitionError` — no `KeyError` crash if a future enum value is added without
   updating the matrix.
3. Check `ALLOWED_TRANSITIONS[current_status]` for `to_status` — raise `IllegalStateTransitionError` if not allowed.
4. If `to_status == DONE`: query `Defect` table for any `status == OPEN` with this `task_id`. If count > 0, raise `DefectBlocksCompletionError` (AD-8).
5. Update `task.status`, `task.updated_at = datetime.now(UTC)` **(RT-4: explicit timestamp).**
6. If `to_status == ARCHIVED`: set `task.handover_context = None` (FR-7, AD-5).
7. Insert `StateTransition` record with `from_status`, `to_status`, `reason`, `worker_id`, `timestamp`.
8. Emit structured log: `INFO` for normal transitions, `WARNING` for BLOCKED transitions.
9. `flush()`.
10. Return the updated task as dict.

**Rules:**

- **RT-19 — explicit creation timestamps.** `Task`, `Epic` and `Defect` have NO `default=` on
  `created_at` or `updated_at`. Every `create_*` method sets `created_at = datetime.now(UTC)` (and
  `updated_at` for Task/Epic); `StateTransition.timestamp` too. Otherwise:
  `IntegrityError: NOT NULL constraint failed`. Pattern: `WorkspaceRepository.register_project()`
  (store.py:82).
- **RT-4 & RT-23 — explicit `updated_at`.** `update_task`, `transition_state`,
  `update_handover_context` and `close_epic` set `entity.updated_at = datetime.now(UTC)` before
  `flush()`. There is no `onupdate` hook on the column.
- **RT-13 — cross-entity integrity.** If `create_task` gets an `epic_id`, the Epic must have the same
  `project_name`, else `ValueError("Epic belongs to a different project")`.
- **RT-3 & RT-14 — title validation.** `create_task`, `create_epic`, `create_defect` and
  `update_task` (if title is not None) call `_validate_non_empty("title", title)` before mutating.
  `nullable=False` does NOT reject empty strings.
- **RT-10 — defect logging (NFR-8).** `create_defect` emits
  `logger.info("Defect created: task_id=%s, defect_id=%s, title=%s", ...)`; `resolve_defect` emits
  `logger.info("Defect resolved: defect_id=%s, task_id=%s", ...)`.
- **RT-17 & RT-18 — boundaries.** No semantic validation of `TransitionReason` (it belongs in the Flow
  orchestrator). No `delete_*` methods: hard deletion destroys the forensic audit trail; use
  `ARCHIVED`/`RESOLVED` states instead.
- **`version`**: set to `1` on creation, never incremented here — reserved for SF-03's OCC
  `acquire_task` against dual acquisition.
- **`attempt_count`**: set to `0` on creation, never modified here — owned by SF-04's zombie recovery
  and circuit breaker.
- **RT-2 — known gap.** The defect check (step 4) and status update (step 5) are non-atomic within
  one `flush()`. SQLite's WAL write serialization and `NullPool` connection isolation mitigate it in
  practice; SF-03's transactional OCC closes it for multi-process access.
- **RT-6 — `list_*` convention.** `list_tasks` and `list_epics` return `[]` for nonexistent project
  names and do NOT raise `ValueError`, like `WorkspaceRepository.get_standards()`. Callers check
  project existence separately if needed.

Serialization helper (private, shared by all return dicts — **RT-5: UUIDs converted to `str()`**):

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

`_epic_to_dict`, `_defect_to_dict`, `_transition_to_dict` follow the same shape. UUID fields use
`str()` (RT-5); Enum fields (e.g. `transition.from_status`, `transition.reason`) use `.value` so
`json.dumps()` does not crash (RT-16).

| File | Change | FR |
|------|--------|-----|
| `src/specweaver/workspace/memory/repository.py` | new — `MemoryRepository` class, 16 methods | FR-4, FR-7 |
| `src/specweaver/workspace/memory/errors.py` | new — `IllegalStateTransitionError`, `DefectBlocksCompletionError` | FR-4 |
| `tests/unit/workspace/test_memory_repository.py` | new — 55 repository-level tests | all |

## Tests

`tests/unit/workspace/test_memory_repository.py` reuses the `engine`/`session`/`base_project`
fixture pattern from `test_memory_store.py` (SF-01), with `@pytest.mark.asyncio` class-based
grouping. `test_create_task_epic_project_mismatch` (test #5, RT-25) needs an Epic from a second
project; it creates that project inline, not via a shared fixture.

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


Tests 49 & 50 parametrize over ALL 30 cells (6×5 excluding diagonal) of the State Transition
Matrix; each `(from, to)` pair must either succeed or raise `IllegalStateTransitionError`.

```bash
pytest tests/unit/workspace/test_memory_repository.py -v
pytest tests/unit/workspace/test_memory_store.py -v    # regression check
tach check
mypy src/specweaver/workspace/memory/repository.py src/specweaver/workspace/memory/errors.py --ignore-missing-imports
ruff check src/specweaver/workspace/memory/
```

Also: `tach check` passes without `tach.toml` changes (new files fall under the existing
`src.specweaver.workspace` boundary); full regression `pytest` (all 4554+ tests pass).

## Decisions (audit)

All 10 findings from the audit were reviewed and approved by HITL on 2026-05-06.

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

HITL action items:

- **Finding #1:** `FlowRepository` still shares `core/flow/store.py` with its schema; refactor it to
  the same split. **Tech Debt: TECH-006** — move it into `core/flow/repository.py`, matching the
  `workspace/memory/` separation. Low priority, no functional impact.
- **Finding #4:** document the pre-validation pattern (SELECT before INSERT → clean `ValueError`
  instead of opaque `IntegrityError`) in `docs/dev_guides/special_patterns_and_adaptations.md` as a
  DB-portability concern: if SpecWeaver migrates from SQLite to PostgreSQL it may need revisiting, since Postgres
  gives richer error codes.
- **Finding #6:** an **MVP Decision Register** — a living document of decisions acceptable for MVP
  that may need changing at production scale — as `docs/roadmap/mvp_decision_register.md`. First
  entries: no pagination on `list_*` methods, the pre-validation SELECT pattern.

Red Team / Blue Team findings accepted and merged:

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
| RT-23 | `close_epic` missing from `updated_at` rule | Added `close_epic` to explicit timestamp rule |
| RT-25 | RT-13 test needs second project in fixture | Documented inline setup for cross-project test |

## As built (2026-05-06)

- 62 unit tests and 10 integration/e2e simulation tests; fully typed; pre-commit gates passed.
- **Since moved** (`fde43dec`, 2026-05-07): `repository.py` became the package
  `workspace/memory/repository/` (`core.py`, `dag.py`, `resilience.py`, with an `__init__.py`); the
  unit tests are split into `test_memory_repository_core.py`, `_dag.py`, `_resilience.py`. Line
  refs above are as of the plan's date.
