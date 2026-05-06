# Implementation Plan: Agent Memory Bank [SF-4: Resilience & Recovery]
- **Feature ID**: B-INTL-09
- **Sub-Feature**: SF-4 — Resilience & Recovery
- **Design Document**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-4
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/B-INTL-09/B-INTL-09_sf4_implementation_plan.md
- **Status**: DRAFT

---

## Scope Summary

SF-4 implements three resilience mechanisms on top of the `MemoryRepository` foundation (SF-2) and the DAG/OCC extensions (SF-3):

1. **Zombie Recovery (`recycle_zombies`)** — Scans for tasks with `status = IN_PROGRESS` where `now() - last_heartbeat_at > 15 minutes` (NFR-4). Resets them to `PENDING`, increments `attempt_count`, clears `assigned_worker_id`, `locked_at`, and `last_heartbeat_at`. Records a `StateTransition` with reason `ZOMBIE_TIMEOUT`. Emits `INFO` structured log.

2. **3-Strike Circuit Breaker (`circuit_breaker`)** — During zombie recycling, if `attempt_count >= 3` after increment, auto-transitions the task to `BLOCKED` (not `PENDING`), creates an auto-generated `Defect` with title `"circuit_breaker: max retries exceeded"`, and emits an `ERROR` structured log. The task is permanently halted from automatic retries.

3. **Upstream DAG Propagation (`propagate_blocked` / `clear_upstream_blocked`)** — When a task transitions to `BLOCKED`, all tasks that list it as a `child_task_id` in `TaskDependency` (i.e., upstream parents that depend on it) are automatically transitioned to `UPSTREAM_BLOCKED` with reason `UPSTREAM_BLOCKED`. Conversely, when a `BLOCKED` task is unblocked (transitions to `PENDING`), all `UPSTREAM_BLOCKED` parents are reverse-propagated back to `PENDING` with reason `UPSTREAM_CLEARED`, but **only if all their other children are also no longer blocked**.

**FRs covered**: FR-5 (Zombie Recovery), FR-8 (Circuit Breaker), FR-9 (Deadlock Propagation).

**FRs explicitly NOT covered**: FR-1–FR-4, FR-6, FR-7 (completed in SF-1/SF-2/SF-3).

**Inputs**: The `MemoryRepository` CRUD + state machine from SF-2, the DAG from SF-3.
**Outputs**:
- `src/specweaver/workspace/memory/repository.py` (modified — add `recycle_zombies`, `pulse_heartbeat`, `propagate_blocked`, `clear_upstream_blocked`)
- `tests/unit/workspace/test_memory_repository.py` (modified — add SF-4 unit tests)
- `tests/integration/workspace/test_memory_integration.py` (modified — add SF-4 integration + E2E tests)
- `docs/dev_guides/agent_memory_state_tracking.md` (modified — add resilience sections)

---

## Research Notes

### Codebase Pattern Analysis

1. **Existing `transition_state`** (repository.py:439-511): The state machine enforcer already handles `BLOCKED` → clears `locked_at`, `last_heartbeat_at`, increments `attempt_count`. SF-4's `recycle_zombies` must use `transition_state` internally to reuse this enforcement, **not** bypass it with raw SQL.

2. **Existing `insert_dependency`** (repository.py:368-408): The DAG junction table `memory_task_dependencies` uses `parent_task_id` / `child_task_id` columns. For propagation, a "parent" is upstream (depends on the child completing). When a child becomes `BLOCKED`, its parents (rows where `child_task_id == blocked_task.id`) should be marked `UPSTREAM_BLOCKED`.

3. **Existing indexes** (store.py:126-127): `idx_task_heartbeat` on `(status, last_heartbeat_at)` — directly supports the zombie scan query. `idx_dep_child` on `(child_task_id)` — supports the propagation query to find parents. `idx_dep_parent` on `(parent_task_id)` — supports the reverse-clear query.

4. **Session lifecycle**: Repository uses `session.flush()`, never `session.commit()`. Transaction boundary is caller-managed.

5. **Logging convention**: `logger = logging.getLogger(__name__)`, `%s` lazy formatting (Pattern #20 from `special_patterns_and_adaptations.md`).

6. **Explicit timestamps**: `datetime.now(UTC)` set explicitly in every mutation (Pattern #14 from `special_patterns_and_adaptations.md`).

7. **Return convention**: All public methods return `dict[str, object]` or `list[dict[str, object]]`.

8. **Error classes**: `IllegalStateTransitionError`, `DefectBlocksCompletionError`, `CyclicDependencyError`, `StaleTaskVersionError` all in `errors.py`. No new error types are needed for SF-4.

9. **`SELECT FOR UPDATE` inapplicable**: SQLite does not support `SELECT FOR UPDATE` natively. The existing OCC pattern (version column) and SQLite's serialized write access handle concurrency. The zombie scan is intended to run from a single orchestrator, not multiple competing workers.

10. **`tach.toml`**: `src.specweaver.workspace` has `depends_on = []`. All imports stay within `workspace.memory.*`, `workspace.store`, and `core.config.database`. No boundary violations.

### External API Research

1. **SQLAlchemy `select().where()` for heartbeat comparison**: Use `Task.last_heartbeat_at < threshold` where `threshold = datetime.now(UTC) - timedelta(minutes=15)`. The `StrictISODateTime` type adapter handles the comparison correctly in SQLite.

2. **No new dependencies**: SF-4 uses only `sqlalchemy`, `datetime`, `logging`, and `uuid` — all already in the codebase.

3. **`WITH RECURSIVE` for propagation**: Already proven in SF-3 for cycle detection. The upstream propagation will use a non-recursive query first (find direct parents), then optionally recurse for multi-hop propagation. However, per FR-9, propagation is explicitly defined as "dynamically flag all upstream parent tasks" — this implies recursive traversal of the entire dependency graph above the blocked task.

---

## Proposed Changes

### Component: Repository (resilience methods)

#### [MODIFY] [repository.py](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/memory/repository.py)

Add four new public methods to `MemoryRepository`:

---

##### Method 1: `pulse_heartbeat(task_id: UUID) -> dict[str, object]`

**Purpose**: Update `last_heartbeat_at` for an IN_PROGRESS task to prevent zombie collection.

```python
async def pulse_heartbeat(self, task_id: uuid.UUID) -> dict[str, object]:
    """Update last_heartbeat_at for an active task (FR-3, NFR-4).

    Only IN_PROGRESS tasks may pulse heartbeats.
    """
    task = await self.session.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")

    if task.status != TaskStatus.IN_PROGRESS:
        raise ValueError(
            f"Cannot pulse heartbeat for task {task_id}: "
            f"status is {task.status.value}, expected IN_PROGRESS"
        )

    task.last_heartbeat_at = datetime.now(UTC)
    task.updated_at = task.last_heartbeat_at
    await self.session.flush()

    logger.debug(
        "Heartbeat pulse: task_id=%s, worker_id=%s",
        task_id,
        task.assigned_worker_id,
    )
    return self._task_to_dict(task)
```

> [!NOTE]
> Heartbeat pulsing is a lightweight operation. It does NOT increment `version` (no OCC needed — only the owning worker pulses its own tasks). It logs at `DEBUG` level per NFR-8.

---

##### Method 2: `recycle_zombies(project_name: str, timeout_minutes: int = 15) -> list[dict[str, object]]`

**Purpose**: Scan for stale IN_PROGRESS tasks and either reset them to PENDING or trigger the circuit breaker (FR-5, FR-8, AD-9).

```python
async def recycle_zombies(
    self, project_name: str, timeout_minutes: int = 15
) -> list[dict[str, object]]:
    """Scan for zombie tasks and recycle or circuit-break them (FR-5, FR-8).

    Zombie criteria: status=IN_PROGRESS AND
        now() - last_heartbeat_at > timeout_minutes.

    For each zombie:
    - If attempt_count < 3 after increment: reset to PENDING (ZOMBIE_TIMEOUT).
    - If attempt_count >= 3 after increment: auto-BLOCKED + Defect (CIRCUIT_BREAKER).

    Returns list of recycled/blocked task dicts.
    """
    threshold = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
    stmt = (
        select(Task)
        .where(
            Task.project_name == project_name,
            Task.status == TaskStatus.IN_PROGRESS,
            Task.last_heartbeat_at < threshold,
        )
    )
    result = await self.session.execute(stmt)
    zombies = result.scalars().all()

    recycled: list[dict[str, object]] = []
    for zombie in zombies:
        # Increment attempt_count first to decide circuit breaker
        zombie.attempt_count += 1
        now = datetime.now(UTC)

        if zombie.attempt_count >= 3:
            # Circuit Breaker (FR-8, AD-9): auto-BLOCKED
            zombie.status = TaskStatus.BLOCKED
            zombie.assigned_worker_id = None
            zombie.locked_at = None
            zombie.last_heartbeat_at = None
            zombie.updated_at = now

            transition = StateTransition(
                task_id=zombie.id,
                from_status=TaskStatus.IN_PROGRESS,
                to_status=TaskStatus.BLOCKED,
                reason=TransitionReason.CIRCUIT_BREAKER,
                timestamp=now,
            )
            self.session.add(transition)

            # Auto-create defect
            defect = Defect(
                task_id=zombie.id,
                title="circuit_breaker: max retries exceeded",
                description=(
                    f"Task {zombie.id} has failed {zombie.attempt_count} times. "
                    "Automatic circuit breaker activated."
                ),
                status=DefectStatus.OPEN,
                created_at=now,
            )
            self.session.add(defect)

            logger.error(
                "Circuit breaker activated: task_id=%s, attempt_count=%s, "
                "project=%s",
                zombie.id,
                zombie.attempt_count,
                project_name,
            )
        else:
            # Normal zombie recycling (FR-5): reset to PENDING
            zombie.status = TaskStatus.PENDING
            zombie.assigned_worker_id = None
            zombie.locked_at = None
            zombie.last_heartbeat_at = None
            zombie.updated_at = now

            transition = StateTransition(
                task_id=zombie.id,
                from_status=TaskStatus.IN_PROGRESS,
                to_status=TaskStatus.PENDING,
                reason=TransitionReason.ZOMBIE_TIMEOUT,
                timestamp=now,
            )
            self.session.add(transition)

            logger.info(
                "Zombie recycled: task_id=%s, attempt_count=%s, project=%s",
                zombie.id,
                zombie.attempt_count,
                project_name,
            )

        recycled.append(self._task_to_dict(zombie))

    await self.session.flush()
    return recycled
```

> [!IMPORTANT]
> **Design Decision: Bypass `transition_state` intentionally.**
> `recycle_zombies` does NOT call `transition_state` internally because:
> 1. `transition_state` increments `attempt_count` on ANY `BLOCKED` transition, but the circuit breaker needs to increment ONCE, then check. Reusing `transition_state` would double-increment.
> 2. `recycle_zombies` operates on a batch of tasks in a single flush. Calling `transition_state` per-task would cause N separate flushes.
> 3. The method still creates `StateTransition` records manually for the audit trail.
> This is a self-contained resilience operation with its own state mutation logic.

---

##### Method 3: `propagate_blocked(task_id: UUID) -> list[dict[str, object]]`

**Purpose**: When a task becomes BLOCKED, cascade UPSTREAM_BLOCKED to all upstream parents (FR-9, AD-11).

```python
async def propagate_blocked(self, task_id: uuid.UUID) -> list[dict[str, object]]:
    """Cascade UPSTREAM_BLOCKED to upstream parent tasks (FR-9, AD-11).

    Finds all direct parents (tasks that have this task_id as their child_task_id)
    and transitions eligible ones to UPSTREAM_BLOCKED.

    Only PENDING and IN_PROGRESS parents are eligible for UPSTREAM_BLOCKED propagation
    (matching the State Transition Matrix: PENDING -> UPSTREAM_BLOCKED is allowed).
    IN_PROGRESS parents cannot transition to UPSTREAM_BLOCKED per the matrix,
    so they are skipped with a warning.

    Returns list of affected parent task dicts.
    """
    # Find direct upstream parents
    stmt = (
        select(TaskDependency.parent_task_id)
        .where(TaskDependency.child_task_id == task_id)
    )
    result = await self.session.execute(stmt)
    parent_ids = [row[0] for row in result.fetchall()]

    affected: list[dict[str, object]] = []
    now = datetime.now(UTC)

    for parent_id in parent_ids:
        parent = await self.session.get(Task, parent_id)
        if parent is None:
            continue

        # Only PENDING tasks can transition to UPSTREAM_BLOCKED per the matrix
        if parent.status != TaskStatus.PENDING:
            if parent.status == TaskStatus.IN_PROGRESS:
                logger.warning(
                    "Skipping propagation: parent task %s is IN_PROGRESS, "
                    "cannot transition to UPSTREAM_BLOCKED per state matrix",
                    parent_id,
                )
            continue

        parent.status = TaskStatus.UPSTREAM_BLOCKED
        parent.updated_at = now

        transition = StateTransition(
            task_id=parent_id,
            from_status=TaskStatus.PENDING,
            to_status=TaskStatus.UPSTREAM_BLOCKED,
            reason=TransitionReason.UPSTREAM_BLOCKED,
            timestamp=now,
        )
        self.session.add(transition)

        logger.info(
            "Upstream propagation: parent=%s blocked by child=%s",
            parent_id,
            task_id,
        )
        affected.append(self._task_to_dict(parent))

    await self.session.flush()
    return affected
```

> [!NOTE]
> **Direct parents only vs. recursive**: FR-9 says "dynamically flag all upstream parent tasks". However, in a DAG, a parent's parent is only transitively blocked if the parent itself becomes blocked. Since `propagate_blocked` only transitions PENDING parents to UPSTREAM_BLOCKED (not a blocked state that would trigger further propagation), the cascading effect must be applied **per-level**. If multi-level cascading is needed, the orchestrator should call `propagate_blocked` on the newly UPSTREAM_BLOCKED parents as well. This keeps the repository method simple and testable.
>
> **Alternative considered**: A `WITH RECURSIVE` CTE to find all transitive ancestors. Rejected because UPSTREAM_BLOCKED is not BLOCKED — it doesn't trigger further cascading by definition. The orchestrator can iterate if needed.

---

##### Method 4: `clear_upstream_blocked(task_id: UUID) -> list[dict[str, object]]`

**Purpose**: When a BLOCKED task is unblocked, reverse-propagate to clear UPSTREAM_BLOCKED on parents (FR-9, AD-11).

```python
async def clear_upstream_blocked(self, task_id: uuid.UUID) -> list[dict[str, object]]:
    """Reverse-propagate: clear UPSTREAM_BLOCKED on parents when blocker resolves (FR-9).

    Only clears a parent if ALL of its children are no longer BLOCKED or
    UPSTREAM_BLOCKED (the parent has no remaining blockers).

    Returns list of cleared parent task dicts.
    """
    # Find direct upstream parents
    stmt = (
        select(TaskDependency.parent_task_id)
        .where(TaskDependency.child_task_id == task_id)
    )
    result = await self.session.execute(stmt)
    parent_ids = [row[0] for row in result.fetchall()]

    cleared: list[dict[str, object]] = []
    now = datetime.now(UTC)

    for parent_id in parent_ids:
        parent = await self.session.get(Task, parent_id)
        if parent is None or parent.status != TaskStatus.UPSTREAM_BLOCKED:
            continue

        # Check ALL children of this parent — are any still blocked?
        children_stmt = (
            select(TaskDependency.child_task_id)
            .where(TaskDependency.parent_task_id == parent_id)
        )
        children_result = await self.session.execute(children_stmt)
        child_ids = [row[0] for row in children_result.fetchall()]

        all_clear = True
        for child_id in child_ids:
            child = await self.session.get(Task, child_id)
            if child is not None and child.status in (
                TaskStatus.BLOCKED,
                TaskStatus.UPSTREAM_BLOCKED,
            ):
                all_clear = False
                break

        if not all_clear:
            logger.debug(
                "Parent %s still has blocked children, skipping clear",
                parent_id,
            )
            continue

        parent.status = TaskStatus.PENDING
        parent.updated_at = now

        transition = StateTransition(
            task_id=parent_id,
            from_status=TaskStatus.UPSTREAM_BLOCKED,
            to_status=TaskStatus.PENDING,
            reason=TransitionReason.UPSTREAM_CLEARED,
            timestamp=now,
        )
        self.session.add(transition)

        logger.info(
            "Upstream cleared: parent=%s unblocked after child=%s resolved",
            parent_id,
            task_id,
        )
        cleared.append(self._task_to_dict(parent))

    await self.session.flush()
    return cleared
```

> [!IMPORTANT]
> **Critical invariant**: `clear_upstream_blocked` checks ALL children of the parent, not just the one that was unblocked. This prevents premature unblocking when a parent depends on multiple children and only one is resolved.

---

### Component: Unit Tests

#### [MODIFY] [test_memory_repository.py](file:///c:/development/pitbula/specweaver/tests/unit/workspace/test_memory_repository.py)

Add a new test class `TestMemoryRepositoryResilience` with the following unit tests:

| # | Test Name | Category | Scenario |
|---|-----------|----------|----------|
| U-1 | `test_pulse_heartbeat_happy_path` | Happy Path | Pulses IN_PROGRESS task; `last_heartbeat_at` updated |
| U-2 | `test_pulse_heartbeat_not_in_progress` | Boundary | Raises ValueError for PENDING task |
| U-3 | `test_pulse_heartbeat_not_found` | Boundary | Raises ValueError for unknown UUID |
| U-4 | `test_recycle_zombies_happy_path` | Happy Path | 1 zombie task recycled to PENDING, `attempt_count` = 1 |
| U-5 | `test_recycle_zombies_no_zombies` | Boundary | Fresh tasks are not recycled (returns empty list) |
| U-6 | `test_recycle_zombies_circuit_breaker` | Critical | Task with `attempt_count=2`, after zombie recycling becomes BLOCKED with defect |
| U-7 | `test_recycle_zombies_clears_worker_fields` | Edge Case | `assigned_worker_id`, `locked_at`, `last_heartbeat_at` all None after recycling |
| U-8 | `test_recycle_zombies_creates_audit_trail` | NFR-8 | `StateTransition` with `ZOMBIE_TIMEOUT` reason exists after recycling |
| U-9 | `test_recycle_zombies_circuit_breaker_audit_trail` | NFR-8 | `StateTransition` with `CIRCUIT_BREAKER` reason + `Defect` with correct title |
| U-10 | `test_recycle_zombies_batch` | Batch | 3 zombies recycled in a single call |
| U-11 | `test_recycle_zombies_custom_timeout` | Config | `timeout_minutes=5` uses different threshold |
| U-12 | `test_propagate_blocked_happy_path` | Happy Path | Child BLOCKED → parent PENDING transitions to UPSTREAM_BLOCKED |
| U-13 | `test_propagate_blocked_no_parents` | Boundary | Task with no upstream parents → returns empty list |
| U-14 | `test_propagate_blocked_parent_already_blocked` | Edge Case | Parent already BLOCKED → skipped |
| U-15 | `test_propagate_blocked_parent_in_progress` | Edge Case | Parent IN_PROGRESS → skipped (matrix does not allow IN_PROGRESS → UPSTREAM_BLOCKED) |
| U-16 | `test_propagate_blocked_creates_audit_trail` | NFR-8 | `StateTransition` with `UPSTREAM_BLOCKED` reason |
| U-17 | `test_clear_upstream_blocked_happy_path` | Happy Path | Blocker resolved → parent UPSTREAM_BLOCKED → PENDING |
| U-18 | `test_clear_upstream_blocked_partial` | Critical | Parent has 2 children; only 1 unblocked → parent stays UPSTREAM_BLOCKED |
| U-19 | `test_clear_upstream_blocked_all_clear` | Happy Path | Parent has 2 children; both unblocked → parent transitions to PENDING |
| U-20 | `test_clear_upstream_blocked_creates_audit_trail` | NFR-8 | `StateTransition` with `UPSTREAM_CLEARED` reason |
| U-21 | `test_clear_upstream_blocked_no_upstream_blocked_parents` | Boundary | No UPSTREAM_BLOCKED parents → returns empty list |
| U-22 | `test_recycle_zombies_structured_logging` | NFR-8 | `logger.info` emitted for zombie recycling |
| U-23 | `test_circuit_breaker_structured_logging` | NFR-8 | `logger.error` emitted for circuit breaker |
| U-24 | `test_propagate_blocked_structured_logging` | NFR-8 | `logger.info` emitted for upstream propagation |

---

### Component: Integration Tests

#### [MODIFY] [test_memory_integration.py](file:///c:/development/pitbula/specweaver/tests/integration/workspace/test_memory_integration.py)

Add integration and E2E scenarios:

| # | Test Name | Category | Scenario |
|---|-----------|----------|----------|
| INT-11 | `test_int_11_zombie_reaper_full_cycle` | Integration | Create task → acquire → backdate heartbeat → recycle_zombies → verify PENDING + attempt_count=1 → re-acquire → succeed |
| INT-12 | `test_int_12_circuit_breaker_three_strikes` | Integration | Task fails 3 times through recycle_zombies → circuit breaker fires → verify BLOCKED + Defect exists |
| INT-13 | `test_int_13_upstream_propagation_cascade` | Integration | Build A→B→C chain, block C → propagate_blocked(C) → B is UPSTREAM_BLOCKED → propagate_blocked(B.id, if needed manually by orchestrator) → A is UPSTREAM_BLOCKED |
| INT-14 | `test_int_14_reverse_propagation_partial` | Integration | A depends on B and C, B blocked → A UPSTREAM_BLOCKED → C unblocked but B still blocked → A stays UPSTREAM_BLOCKED |
| INT-15 | `test_int_15_reverse_propagation_full_clear` | Integration | Same as INT-14 but B also unblocks → A transitions to PENDING |
| E2E-6 | `test_e2e_6_resilient_dag_execution` | E2E | Full lifecycle: Create Epic + 3 tasks in DAG → T1 completes → T2 zombies → circuit breaker fires → T3 UPSTREAM_BLOCKED → human resolves T2 defect → unblock → T3 resumes → Epic closes |
| E2E-7 | `test_e2e_7_heartbeat_survival` | E2E | Agent acquires task → pulses heartbeat repeatedly → zombie scan runs → task NOT recycled |

---

### Component: Documentation

#### [MODIFY] [agent_memory_state_tracking.md](file:///c:/development/pitbula/specweaver/docs/dev_guides/agent_memory_state_tracking.md)

Add three new sections:

1. **5. Heartbeat Pulsing** — How agents must call `pulse_heartbeat` during long-running work to prevent zombie collection. Cadence recommendation (every 5 minutes).

2. **6. Zombie Recovery & Circuit Breaker** — How the orchestrator calls `recycle_zombies` on a schedule. Explanation of the 3-strike rule and auto-defect creation. How to manually unblock circuit-broken tasks.

3. **7. DAG Propagation** — How `propagate_blocked` and `clear_upstream_blocked` work. When the orchestrator should call them. Multi-level cascading responsibility (orchestrator, not repository).

---

## Commit Boundaries

### CB-1: Heartbeat + Zombie Recovery
- `repository.py`: Add `pulse_heartbeat`, `recycle_zombies` (including circuit breaker logic)
- `test_memory_repository.py`: Add U-1 through U-11, U-22, U-23
- `test_memory_integration.py`: Add INT-11, INT-12, E2E-7

### CB-2: DAG Propagation + Documentation
- `repository.py`: Add `propagate_blocked`, `clear_upstream_blocked`
- `test_memory_repository.py`: Add U-12 through U-21, U-24
- `test_memory_integration.py`: Add INT-13, INT-14, INT-15, E2E-6
- `agent_memory_state_tracking.md`: Add sections 5, 6, 7

---

## Verification Plan

### Automated Tests

```bash
# Unit tests only (SF-4 tests)
pytest tests/unit/workspace/test_memory_repository.py -k "Resilience" -v

# Integration tests only (SF-4 scenarios)
pytest tests/integration/workspace/test_memory_integration.py -k "int_11 or int_12 or int_13 or int_14 or int_15 or e2e_6 or e2e_7" -v

# Full memory bank test suite
pytest tests/unit/workspace/test_memory_repository.py tests/integration/workspace/test_memory_integration.py -v

# Full project test suite
pytest

# Quality gates
ruff check src/specweaver/workspace/memory/
mypy src/specweaver/workspace/memory/repository.py --ignore-missing-imports
tach check
```

### Manual Verification
- Inspect `StateTransition` audit trail after zombie recycling and propagation
- Verify structured log output format matches NFR-8 requirements
- Review documentation sections for correctness and completeness
