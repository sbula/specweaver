# Implementation Plan: Agent Memory Bank [SF-03: DAG & Context Validation]
- **Feature ID**: B-INTL-09
- **Sub-Feature**: SF-03 — DAG & Context Validation
- **Design Document**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_sf03_implementation_plan.md
- **Status**: APPROVED
- **Execution State**: COMPLETED (Commit Boundaries 1, 2, and 3 successfully implemented and verified).

---

## Scope Summary

SF-03 extends the `MemoryRepository` with three capabilities not present in the SF-02 CRUD foundation:

1. **DAG Cycle Detection via `WITH RECURSIVE`** — Replace the naive `add_task_dependency` with `insert_dependency` that executes a `WITH RECURSIVE` CTE against the `memory_task_dependencies` table to detect cycles *before* inserting an edge. This prevents infinite hallucinated cycles from crashing the Flow Engine (AD-7).

2. **Transactional OCC `acquire_task`** — Implement Optimistic Concurrency Control using the `version` column. A SELECT + UPDATE executes within a single transaction. On version mismatch, raise `StaleTaskVersionError` immediately. Retry logic (NFR-1) is deferred to the caller (`FlowEngine`) to ensure a fresh transaction boundary is created for each retry.

3. **Pydantic `HandoverContext` Validation** — Replace the raw string `update_handover_context` with a Pydantic-validated version. Define a `HandoverContext` model with strict JSON schema, field validation, and an 8KB hard limit (NFR-6). Stack traces are truncated to the last 2000 characters. Invalid payloads are rejected *before* they enter the DB.

**FRs covered**: FR-4 (DAG cycle checks + OCC acquire + Pydantic context validation).

**FRs explicitly NOT covered (deferred to SF-04)**:
- Zombie Recovery heartbeat scanning → SF-04
- 3-Strike Circuit Breaker → SF-04
- Upstream `BLOCKED` → `UPSTREAM_BLOCKED` DAG propagation → SF-04

**Inputs**: The `MemoryRepository` core CRUD from SF-02 (`repository.py`), the SQLAlchemy models from SF-01 (`store.py`).

**Outputs**:
- `src/specweaver/workspace/memory/repository.py` (modified — add `insert_dependency`, `acquire_task`, upgrade `update_handover_context`)
- `src/specweaver/workspace/memory/errors.py` (modified — add `CyclicDependencyError`, `StaleTaskVersionError`)
- `src/specweaver/workspace/memory/models.py` (new — `HandoverContext` Pydantic model)
- `tests/unit/workspace/test_memory_repository.py` (modified — add SF-03 tests)
- `tests/integration/workspace/test_memory_integration.py` (modified — add SF-03 integration scenarios)

---

## Research Notes

### Codebase Pattern Analysis

1. **Existing `add_task_dependency`**: SF-02 implemented a basic version at `repository.py:269-284` that checks for self-dependency and duplicate edges but does NOT perform `WITH RECURSIVE` cycle detection. SF-03 must **replace** this method with `insert_dependency` that includes cycle checks, OR rename and extend the existing one.

2. **Existing `update_handover_context`**: SF-02 implemented a raw string setter at `repository.py:258-267`. It accepts `str | None` and stores directly. SF-03 must **upgrade** this to validate through a Pydantic model and enforce the 8KB limit at the application boundary. The DB already has a `CheckConstraint("length(handover_context) <= 8192")` as a safety net (SF-01).

3. **No `__init__.py`**: PEP 420 implicit namespace package. No `__init__.py` files.

4. **Return pattern**: All repository methods return `dict[str, object]` per codebase convention.

5. **Logging convention**: `logger = logging.getLogger(__name__)` with `%s` lazy formatting (Pattern #20).

6. **Explicit timestamps**: All mutation methods must set `datetime.now(UTC)` explicitly (Pattern #14 in `special_patterns_and_adaptations.md`).

7. **Session lifecycle**: Repository uses `session.flush()`, NOT `session.commit()`. Transaction boundary is managed by `session_scope()`.

8. **`tach.toml`**: `src.specweaver.workspace` is registered with `depends_on = []`. The new code stays within the existing boundary — it only imports from `workspace.memory.store`, `workspace.store`, and `core.config.database`.

### External API Research

1. **SQLAlchemy `text()` + `WITH RECURSIVE`**: Use `sqlalchemy.text()` with named bind parameters (`:parent_id`, `:child_id`) for the recursive CTE. Execute via `await session.execute(text(...), {"parent_id": ..., "child_id": ...})`. Results via `result.scalars().all()` or `result.fetchone()`.

2. **OCC Pattern**: SQLAlchemy 2.0's native `version_id_col` mapper arg auto-increments version on every flush, which is too aggressive. SF-03 will manually check `version` in a WHERE clause during `acquire_task` and increment only on successful acquisition.

3. **Pydantic v2**: Project uses `pydantic>=2.12`. Use `BaseModel` with `Field(max_length=...)` for field constraints. Use `model_validate_json()` for JSON string validation. Use `@field_validator` with `mode="after"` to guarantee type safety for stack trace truncation.

4. **Retry & Backoff boundary**: Retry logic should be handled by the caller creating a new `session_scope()`. Implementing backoff inside the `MemoryRepository` violates transaction snapshot isolation on SQLite, causing infinite retries on stale data.

5. **`StaleDataError`**: SQLAlchemy provides `sqlalchemy.orm.exc.StaleDataError` but we won't use the mapper-level OCC. We'll define a custom `StaleTaskVersionError` that mirrors `IllegalStateTransitionError` pattern — includes `task_id`, `expected_version`, `actual_version`.

### Pydantic Version Compatibility

- `pydantic>=2.12` is confirmed in `pyproject.toml:15`.
- No new dependencies required. Pydantic is already a project dependency.

---

## Proposed Changes

### Component 1: Error Layer

#### [MODIFY] errors.py — `src/specweaver/workspace/memory/errors.py`

**Change**: Add 2 new domain exceptions for SF-03.

```python
class CyclicDependencyError(Exception):
    """Raised when inserting a dependency would create a cycle in the DAG (AD-7).

    Attributes:
        parent_task_id: The UUID of the parent task.
        child_task_id: The UUID of the child task.
    """

    def __init__(self, parent_task_id: uuid.UUID, child_task_id: uuid.UUID) -> None:
        self.parent_task_id = parent_task_id
        self.child_task_id = child_task_id
        super().__init__(
            f"Cyclic dependency detected: inserting edge "
            f"{parent_task_id} → {child_task_id} would create a cycle"
        )


class StaleTaskVersionError(Exception):
    """Raised when OCC version mismatch prevents task acquisition (AD-6).

    Attributes:
        task_id: The UUID of the task.
        expected_version: The version the caller expected.
        actual_version: The current version in the DB.
    """

    def __init__(self, task_id: uuid.UUID, expected_version: int, actual_version: int) -> None:
        self.task_id = task_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Stale version for task {task_id}: "
            f"expected {expected_version}, found {actual_version}"
        )
```

---

### Component 2: Pydantic Validation Model

#### [NEW] models.py — `src/specweaver/workspace/memory/models.py`

**Purpose**: Define the `HandoverContext` Pydantic model that enforces NFR-5 (strict typed JSON) and NFR-6 (8KB limit).

```python
"""Agent Memory Bank — Pydantic validation models.

Defines HandoverContext for strict JSON schema validation
of the handover_context field (NFR-5, NFR-6).
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


_MAX_CONTEXT_BYTES = 8192  # 8KB hard limit (NFR-6)
_MAX_STACK_TRACE_CHARS = 2000  # Truncation limit for stack traces
_ALLOWED_PRIMITIVE_TYPES = (str, int, float, bool)


class HandoverContext(BaseModel):
    """Strict schema for task handover context.

    Bounded to factual telemetry to prevent hallucination transfer (NFR-5).
    Total serialized size must not exceed 8KB (NFR-6).
    """

    files_touched: list[str] = Field(default_factory=list, description="Files modified during this task")
    errors_encountered: list[str] = Field(default_factory=list, description="Error messages hit during execution")
    stack_trace: str | None = Field(default=None, description="Last stack trace, truncated to 2000 chars")
    summary: str | None = Field(default=None, max_length=2000, description="Free-form summary of progress")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional key-value telemetry")

    @field_validator("stack_trace", mode="after")
    @classmethod
    def truncate_stack_trace(cls, v: str | None) -> str | None:
        """Truncate stack traces to last 2000 characters (NFR-6)."""
        if v is not None and len(v) > _MAX_STACK_TRACE_CHARS:
            return v[-_MAX_STACK_TRACE_CHARS:]
        return v

    @field_validator("metadata", mode="after")
    @classmethod
    def validate_metadata_primitives(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Reject non-primitive values to prevent deeply nested hallucination payloads."""
        for key, val in v.items():
            if isinstance(val, list):
                if not all(isinstance(item, _ALLOWED_PRIMITIVE_TYPES) for item in val):
                    raise ValueError(
                        f"metadata['{key}'] contains a list with non-primitive elements"
                    )
            elif not isinstance(val, _ALLOWED_PRIMITIVE_TYPES):
                raise ValueError(
                    f"metadata['{key}'] must be a primitive (str, int, float, bool) "
                    f"or a flat list of primitives, got {type(val).__name__}"
                )
        return v

    def to_json_str(self) -> str:
        """Serialize to JSON string, enforcing 8KB limit and stripping None values.

        Raises:
            ValueError: If serialized context exceeds 8KB.
        """
        serialized = self.model_dump_json(exclude_none=True)
        if len(serialized.encode("utf-8")) > _MAX_CONTEXT_BYTES:
            raise ValueError(
                f"Serialized handover context exceeds {_MAX_CONTEXT_BYTES} byte limit "
                f"({len(serialized.encode('utf-8'))} bytes)"
            )
        return serialized

    @classmethod
    def from_json_str(cls, json_str: str) -> "HandoverContext":
        """Deserialize from JSON string with validation."""
        return cls.model_validate_json(json_str)
```

> [!NOTE]
> **Hallucination Mitigation**: The `HandoverContext` model intentionally restricts fields to factual telemetry (`files_touched`, `errors_encountered`, `stack_trace`). Free-form text is limited to `summary` with a 2000-char cap. The `metadata` dict accepts `str`, `int`, `float`, `bool`, or flat lists of those types — enforced by the `validate_metadata_primitives` validator to prevent deeply nested hallucination payloads.

---

### Component 3: Repository Extensions

#### [MODIFY] repository.py — `src/specweaver/workspace/memory/repository.py`

**Changes**:

##### 3a. Replace `add_task_dependency` with `insert_dependency` (WITH RECURSIVE cycle check)

The existing `add_task_dependency` at lines 269-284 will be **replaced** with `insert_dependency` that performs a `WITH RECURSIVE` CTE cycle check before inserting the edge.

```python
async def insert_dependency(self, parent_id: uuid.UUID, child_id: uuid.UUID) -> None:
    """Add a task dependency with WITH RECURSIVE cycle detection (AD-7).

    Checks that adding parent → child does not create a cycle.
    A cycle exists if child is already reachable as an ancestor of parent.

    Raises:
        ValueError: If self-dependency or duplicate edge.
        CyclicDependencyError: If insertion would create a cycle.
    """
    if parent_id == child_id:
        raise ValueError("Cannot add self-dependency")

    # 1. Verify both tasks exist
    parent_task = await self.session.get(Task, parent_id)
    if parent_task is None:
        raise ValueError(f"Parent task not found: {parent_id}")
    child_task = await self.session.get(Task, child_id)
    if child_task is None:
        raise ValueError(f"Child task not found: {child_id}")

    # 2. WITH RECURSIVE cycle detection
    # Check: can we reach parent_id by walking UP from child_id?
    # If yes, adding parent → child creates a cycle.
    cycle_check = text("""
        WITH RECURSIVE ancestors(task_id) AS (
            -- Anchor: start from the proposed child
            SELECT :parent_id AS task_id
            UNION ALL
            -- Recursive: walk up through existing parent edges
            SELECT d.parent_task_id
            FROM memory_task_dependencies d
            JOIN ancestors a ON d.child_task_id = a.task_id
        )
        SELECT 1 FROM ancestors WHERE task_id = :child_id LIMIT 1
    """)
    try:
        result = await self.session.execute(
            cycle_check, {"parent_id": parent_id, "child_id": child_id}
        )
        if result.fetchone() is not None:
            raise CyclicDependencyError(parent_id, child_id)
    except OperationalError as e:
        if "recursion depth" in str(e).lower():
            raise ValueError(f"DAG depth limit exceeded while checking cycle: {e}")
        raise

    # 3. Insert the edge (race condition safe via composite PK constraint)
    dep = TaskDependency(parent_task_id=parent_id, child_task_id=child_id)
    self.session.add(dep)
    try:
        await self.session.flush()
    except IntegrityError:
        # Composite PK on (parent_task_id, child_task_id) enforces uniqueness
        raise ValueError("Dependency already exists")

    logger.info(
        "Dependency inserted: parent=%s → child=%s",
        parent_id, child_id
    )
```

> [!CAUTION]
> **`remove_task_dependency`** (lines 286-299) is kept as-is from SF-02. It does not need cycle checks since removing an edge can never create a cycle.

> [!NOTE]
> **SQLite UUID Binding**: Raw `uuid.UUID` objects are passed as bind parameters. SQLAlchemy's type system handles the conversion to the storage format (`CHAR(32)` hex on SQLite). The `WITH RECURSIVE` walks existing edges to check if `child_id` is already an ancestor of `parent_id`.

##### 3b. Add `acquire_task` with OCC + exponential backoff

```python
async def acquire_task(
    self, task_id: uuid.UUID, worker_id: str
) -> dict[str, object]:
    """Acquire a PENDING task using Optimistic Concurrency Control (AD-6, AD-14).

    Performs SELECT + UPDATE within a single transaction.
    Raises StaleTaskVersionError immediately on mismatch so caller can retry.

    Args:
        task_id: The task to acquire.
        worker_id: The worker/agent identifier claiming the task.

    Returns:
        Updated task dict with status=IN_PROGRESS.

    Raises:
        ValueError: If task not found.
        IllegalStateTransitionError: If task is not in PENDING status.
        StaleTaskVersionError: If the task version changed before acquisition.
    """
    task = await self.session.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")

    if task.status != TaskStatus.PENDING:
        raise IllegalStateTransitionError(
            task_id, task.status, TaskStatus.IN_PROGRESS
        )

    expected_version = task.version

    # OCC: UPDATE only if version matches
    now = datetime.now(UTC)
    stmt = (
        update(Task)
        .where(Task.id == task_id, Task.version == expected_version)
        .values(
            status=TaskStatus.IN_PROGRESS,
            assigned_worker_id=worker_id,
            locked_at=now,
            last_heartbeat_at=now,
            version=expected_version + 1,
            updated_at=now,
        )
    )
    result = await self.session.execute(stmt)

    if result.rowcount == 1:
        # Success — record audit trail
        transition = StateTransition(
            task_id=task_id,
            from_status=TaskStatus.PENDING,
            to_status=TaskStatus.IN_PROGRESS,
            reason=TransitionReason.ACQUIRED,
            worker_id=worker_id,
            timestamp=now,
        )
        self.session.add(transition)
        await self.session.flush()

        # Refresh to get updated state
        await self.session.refresh(task)

        logger.info(
            "Task acquired: task_id=%s, worker_id=%s, version=%s",
            task_id, worker_id, expected_version + 1
        )
        return self._task_to_dict(task)

    # Version mismatch — refresh to get actual version, then reject
    await self.session.refresh(task)
    logger.error(
        "OCC collision: task_id=%s, expected_version=%s, actual_version=%s",
        task_id, expected_version, task.version
    )
    raise StaleTaskVersionError(task_id, expected_version, task.version)
```

> [!NOTE]
> **Caller Retry Responsibility**: The `acquire_task` method performs a single OCC attempt and raises `StaleTaskVersionError` immediately on version mismatch. The caller (`FlowEngine`) is responsible for retry logic with exponential backoff + jitter per NFR-1: `sleep(random(0.1, 0.5) * 2^attempt)`. Each retry must create a **new** `session_scope()` to get a fresh transaction snapshot.

##### 3c. Upgrade `update_handover_context` with Pydantic validation

The existing `update_handover_context` at lines 258-267 is **replaced**:

```python
async def update_handover_context(
    self, task_id: uuid.UUID, context: "HandoverContext | None"
) -> dict[str, object]:
    """Update handover context with strict domain boundary enforcement (NFR-5, NFR-6).

    Accepts only a validated HandoverContext model or None to clear.

    Raises:
        ValueError: If task not found or serialization exceeds size limits.
    """
    task = await self.session.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")

    if context is None:
        task.handover_context = None
    else:
        # context is a HandoverContext instance, guaranteed to serialize safely
        task.handover_context = context.to_json_str()

    task.updated_at = datetime.now(UTC)
    await self.session.flush()

    logger.debug(
        "Handover context updated: task_id=%s, size=%s bytes",
        task_id,
        len(task.handover_context.encode("utf-8")) if task.handover_context else 0
    )
    return self._task_to_dict(task)
```

##### 3d. New imports required in repository.py

```python
from sqlalchemy import text, update  # NEW for SF-03
from sqlalchemy.exc import IntegrityError, OperationalError  # NEW for SF-03

from specweaver.workspace.memory.errors import (
    CyclicDependencyError,        # NEW for SF-03
    DefectBlocksCompletionError,
    IllegalStateTransitionError,
    StaleTaskVersionError,         # NEW for SF-03
)
from specweaver.workspace.memory.models import HandoverContext  # NEW for SF-03
```

##### 3e. Deprecation of `add_task_dependency`

The existing `add_task_dependency` method is **replaced** by `insert_dependency`. The old name is removed. The integration tests calling `add_task_dependency` must be updated to use `insert_dependency`.

---

### Component 4: Tests

#### [MODIFY] test_memory_repository.py — `tests/unit/workspace/test_memory_repository.py`

**New test scenarios for SF-03:**

| # | Test | What it verifies | FRs/ADs |
|---|------|------------------|---------|
| U-1 | `test_insert_dependency_happy_path` | Valid edge insertion with cycle check | FR-4, AD-7 |
| U-2 | `test_insert_dependency_self_reference` | Self-dependency rejected | AD-7 |
| U-3 | `test_insert_dependency_duplicate` | Duplicate edge rejected | AD-7 |
| U-4 | `test_insert_dependency_cycle_direct` | A→B then B→A raises `CyclicDependencyError` | AD-7 |
| U-5 | `test_insert_dependency_cycle_transitive` | A→B→C then C→A raises `CyclicDependencyError` | AD-7 |
| U-6 | `test_insert_dependency_diamond_no_cycle` | A→C, B→C (diamond) is valid | AD-7 |
| U-7 | `test_insert_dependency_nonexistent_parent` | Nonexistent parent raises ValueError | AD-7 |
| U-8 | `test_insert_dependency_nonexistent_child` | Nonexistent child raises ValueError | AD-7 |
| U-9 | `test_acquire_task_happy_path` | OCC acquisition increments version, sets worker | AD-6, AD-14, NFR-1 |
| U-10 | `test_acquire_task_not_pending` | Non-PENDING task raises IllegalStateTransitionError | AD-15 |
| U-11 | `test_acquire_task_not_found` | Nonexistent task raises ValueError | FR-4 |
| U-12 | `test_acquire_task_sets_heartbeat` | `locked_at` and `last_heartbeat_at` set on acquire | FR-3 |
| U-13 | `test_acquire_task_audit_trail` | StateTransition created with ACQUIRED reason | AD-16 |
| U-14 | `test_acquire_task_worker_id_recorded` | `assigned_worker_id` set to caller | FR-3 |
| U-15 | `test_handover_context_pydantic_happy_path` | Valid HandoverContext model accepted | NFR-5, NFR-6 |
| U-18 | `test_handover_context_8kb_limit` | Oversized context raises ValueError | NFR-6 |
| U-19 | `test_handover_context_stack_trace_truncation` | Stack trace > 2000 chars truncated | NFR-6 |
| U-20 | `test_handover_context_none_clears` | Passing None sets context to NULL | FR-7 |
| U-21 | `test_handover_context_roundtrip` | Write + read preserves exact data (compare deserialized models, not raw JSON) | NFR-5 |
| U-22 | `test_insert_dependency_long_chain_no_cycle` | 10-node linear chain with no false positive | AD-7 |
| U-23 | `test_acquire_task_version_mismatch` | Manually bump version between GET and UPDATE; assert `StaleTaskVersionError` raised with correct `expected_version` and `actual_version` | AD-6 |

**Pydantic model unit tests** (in a new test section or file):

| # | Test | What it verifies |
|---|------|------------------|
| M-1 | `test_handover_context_model_defaults` | Default empty lists and None fields |
| M-2 | `test_handover_context_model_full` | All fields populated |
| M-3 | `test_handover_context_to_json_str` | Serialization produces valid JSON |
| M-4 | `test_handover_context_from_json_str` | Deserialization roundtrip |
| M-5 | `test_handover_context_truncation` | Stack trace truncated at 2000 |
| M-6 | `test_handover_context_size_limit_exceeded` | to_json_str raises ValueError for oversized |
| M-7 | `test_handover_context_metadata_primitives_only` | Dict values must be primitives (str, int, float, bool) or flat lists; nested dicts/objects rejected |
| M-8 | `test_handover_context_exclude_none_roundtrip` | `to_json_str(exclude_none=True)` → `from_json_str()` preserves model equality |

#### [MODIFY] test_memory_integration.py — `tests/integration/workspace/test_memory_integration.py`

**New integration scenarios:**

| # | Test | What it simulates |
|---|------|-------------------|
| I-1 | `test_int_occ_dual_agent_race` | Two agents poll same task; one succeeds, other gets StaleTaskVersionError |
| I-2 | `test_int_dag_deep_chain_with_cycle_rejection` | 5-node chain + attempted back-edge rejected |
| I-3 | `test_int_handover_context_across_agent_handoff` | Agent 1 writes HandoverContext, Agent 2 reads valid deserialized data |
| I-4 | `test_int_acquire_blocked_task_rejected` | Cannot acquire a BLOCKED task |
| I-5 | `test_int_occ_acquire_then_complete` | Full lifecycle: acquire → work → complete with version tracking |

---

## Verification Plan

### Automated Tests
```bash
# Unit tests (SF-03 specific)
pytest tests/unit/workspace/test_memory_repository.py -v -k "sf3 or insert_dependency or acquire_task or handover_context_pydantic"

# Integration tests
pytest tests/integration/workspace/test_memory_integration.py -v

# Full module regression
pytest tests/unit/workspace/ tests/integration/workspace/ -v

# Quality gates
ruff check src/specweaver/workspace/memory/
mypy src/specweaver/workspace/memory/ --ignore-missing-imports
tach check
```

### Manual Verification
- Inspect the `WITH RECURSIVE` query output in debug mode against a known DAG topology
- Verify OCC collision logging includes correct `expected_version` and `actual_version`

---

## Backlog / Deferred Items

1. **OCC with `session.begin()` nested transactions**: The design says "execute within a single `async with session.begin()` transaction". The current codebase uses `session_scope()`. The `acquire_task` OCC check executes a single UPDATE statement, which inherently acts transactionally. The retry loop has been deferred entirely to the `FlowEngine` caller to preserve `session_scope()` isolation logic.
