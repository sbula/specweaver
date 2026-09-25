# B-INTL-09 SF-04 — Resilience & Recovery

**Status**: DRAFT (plan) — implemented and committed in `fde43dec` (2026-05-07). · **FRs owned**:
FR-5 (Zombie Recovery), FR-8 (Circuit Breaker), FR-9 (Deadlock Propagation) · **Depends on**:
SF-02, SF-03 · Design: [B-INTL-09_design.md](B-INTL-09_design.md) §Sub-features → SF-04

## Goal

Three resilience mechanisms on the SF-02 `MemoryRepository` and the SF-03 DAG/OCC extensions:

1. **Zombie Recovery (`recycle_zombies`)** — finds `status = IN_PROGRESS` tasks where
   `now() - last_heartbeat_at > 15 minutes` OR `last_heartbeat_at IS NULL` (NFR-4, RT-7). Resets
   them to `PENDING`, increments `attempt_count` and `version`, clears `assigned_worker_id`,
   `locked_at` and `last_heartbeat_at`. Records a `StateTransition` with reason `ZOMBIE_TIMEOUT` and
   logs `INFO`. It keeps `handover_context`, so the next agent sees the failure (RT2-2).
2. **3-Strike Circuit Breaker (`circuit_breaker`)** — during zombie recycling, if
   `attempt_count >= 3` after increment, the task goes to `BLOCKED` (not `PENDING`), gets an
   auto-generated `Defect` titled `"circuit_breaker: max retries exceeded"`, and an `ERROR` log. No
   more automatic retries. **Semantics (RT-1):** `attempt_count` counts ALL failure paths (zombie
   recycling AND `transition_state` → BLOCKED); the breaker fires at `>= 3` total failures.
3. **Upstream DAG Propagation (`propagate_blocked` / `clear_upstream_blocked`)** (FR-9, AD-11) —
   when a task goes `BLOCKED`, **all transitive upstream ancestors** go `UPSTREAM_BLOCKED` via BFS
   (RT-4). `propagate_blocked` checks the source is actually `BLOCKED` first (RT2-3). When a
   `BLOCKED` task goes back to `PENDING`, `clear_upstream_blocked` walks the same BFS and returns
   `UPSTREAM_BLOCKED` parents to `PENDING` with reason `UPSTREAM_CLEARED`, **only if all their other
   children are also no longer blocked**. It checks the source is no longer blocked first (RT2-4).

FR-1–FR-4, FR-6, FR-7 are done in SF-01/SF-02/SF-03.

## Where it plugs in

| Fact | Where |
|---|---|
| `transition_state` already handles `BLOCKED`: clears `locked_at`, `last_heartbeat_at`, increments `attempt_count`. `recycle_zombies` bypasses it on purpose (RT2-8) — see the bypass decision below. | `repository.py:439-511` |
| `insert_dependency` / `memory_task_dependencies` use `parent_task_id` / `child_task_id`. A "parent" is upstream (depends on the child completing). When a child goes `BLOCKED`, its parents (rows where `child_task_id == blocked_task.id`) become `UPSTREAM_BLOCKED`. | `repository.py:368-408` |
| `idx_task_heartbeat` on `(status, last_heartbeat_at)` serves the zombie scan; `idx_dep_child` on `(child_task_id)` the propagation query; `idx_dep_parent` on `(parent_task_id)` the reverse clear. | `store.py:126-127` |
| `IllegalStateTransitionError`, `DefectBlocksCompletionError`, `CyclicDependencyError`, `StaleTaskVersionError` all in `errors.py`. No new error types. | `errors.py` |
| `src.specweaver.workspace` has `depends_on = []`. Imports stay within `workspace.memory.*`, `workspace.store`, `core.config.database`. | `tach.toml` |

Conventions carried over: `session.flush()`, never `session.commit()` (caller-managed transaction);
`logger = logging.getLogger(__name__)`, `%s` lazy formatting (Pattern #20 from
`special_patterns_and_adaptations.md`); `datetime.now(UTC)` set explicitly in every mutation
(Pattern #14); public methods return `dict[str, object]` or `list[dict[str, object]]`.

- **No `SELECT FOR UPDATE`**: SQLite does not support it. The OCC `version` column and SQLite's
  serialized writes handle concurrency. The zombie scan runs from a single orchestrator, not from
  competing workers.
- **Heartbeat comparison** (`select().where()`): `Task.last_heartbeat_at < threshold` with
  `threshold = datetime.now(UTC) - timedelta(minutes=15)`; `StrictISODateTime` compares correctly in
  SQLite.
- **No new dependencies**: `sqlalchemy`, `datetime` (incl. `timedelta`), `logging`, `uuid`. The NULL
  heartbeat query needs `sqlalchemy.or_` (RT-7).
- **Propagation depth**: SF-03 proved `WITH RECURSIVE` for cycle detection. FR-9 says "dynamically
  flag all upstream parent tasks", which means traversing the whole graph above the blocked task —
  so propagation walks transitively (BFS over direct-parent queries), not just one hop.

## Changes

`src/specweaver/workspace/memory/repository.py` — four new public methods on `MemoryRepository`,
plus a private builder.

**1. `pulse_heartbeat(task_id: UUID, worker_id: str) -> dict[str, object]`** — refreshes
`last_heartbeat_at` of an IN_PROGRESS task so it is not collected as a zombie. Rejects a worker that
does not own the task (RT-3).

```python
async def pulse_heartbeat(
    self, task_id: uuid.UUID, worker_id: str
) -> dict[str, object]:
    """Update last_heartbeat_at for an active task (FR-3, NFR-4).

    Only IN_PROGRESS tasks may pulse heartbeats.
    The caller must provide the worker_id that owns the task (RT-3).
    """
    task = await self.session.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")

    if task.status != TaskStatus.IN_PROGRESS:
        raise ValueError(
            f"Cannot pulse heartbeat for task {task_id}: "
            f"status is {task.status.value}, expected IN_PROGRESS"
        )

    if task.assigned_worker_id != worker_id:
        raise ValueError(
            f"Worker {worker_id} does not own task {task_id}: "
            f"assigned to {task.assigned_worker_id}"
        )

    task.last_heartbeat_at = datetime.now(UTC)
    task.updated_at = task.last_heartbeat_at
    await self.session.flush()

    logger.debug(
        "Heartbeat pulse: task_id=%s, worker_id=%s",
        task_id,
        worker_id,
    )
    return self._task_to_dict(task)
```

It does NOT increment `version` (no OCC needed — only the owning worker pulses, checked by
`worker_id`). Logs at `DEBUG` per NFR-8.

**0 (private). `_build_defect(task_id, title, description) -> Defect`** — builds a validated `Defect`
without flushing. Shared by `create_defect` and `recycle_zombies`: calling `create_defect` (which
flushes) inside the batch loop would break atomicity (RT2-5).

```python
CIRCUIT_BREAKER_DEFECT_TITLE = "circuit_breaker: max retries exceeded"

def _build_defect(
    self, task_id: uuid.UUID, title: str, description: str | None = None
) -> Defect:
    """Build a validated Defect instance without flushing (RT2-5)."""
    _validate_non_empty("title", title)
    now = datetime.now(UTC)
    return Defect(
        task_id=task_id,
        title=title,
        description=description,
        status=DefectStatus.OPEN,
        created_at=now,
    )
```

> [!NOTE]
> `create_defect` should be refactored to use `_build_defect` internally:
> ```python
> async def create_defect(self, task_id, title, description=None):
>     task = await self.session.get(Task, task_id)
>     if task is None:
>         raise ValueError(f"Task not found: {task_id}")
>     defect = self._build_defect(task_id, title, description)
>     self.session.add(defect)
>     await self.session.flush()
>     logger.info("Defect created: task_id=%s, defect_id=%s, title=%s", task_id, defect.id, title)
>     return self._defect_to_dict(defect)
> ```

**2. `recycle_zombies(project_name: str, timeout_minutes: int = 15, batch_size: int = 100) -> list[dict[str, object]]`**
— resets stale IN_PROGRESS tasks to PENDING or trips the circuit breaker (FR-5, FR-8, AD-9).

```python
async def recycle_zombies(
    self, project_name: str, timeout_minutes: int = 15, batch_size: int = 100
) -> list[dict[str, object]]:
    """Scan for zombie tasks and recycle or circuit-break them (FR-5, FR-8).

    Zombie criteria: status=IN_PROGRESS AND
        (now() - last_heartbeat_at > timeout_minutes OR last_heartbeat_at IS NULL).

    For each zombie:
    - If attempt_count < 3 after increment: reset to PENDING (ZOMBIE_TIMEOUT).
    - If attempt_count >= 3 after increment: auto-BLOCKED + Defect (CIRCUIT_BREAKER).

    Note: timeout_minutes=0 acts as a force-recycle-all operation (RT2-12).

    Returns list of recycled/blocked task dicts. Each dict includes a
    'resilience_action' key: 'RECYCLED' or 'CIRCUIT_BREAKER' (RT2-7).
    """
    # RT-2: Defensive guard — verify our transitions are still legal per the matrix
    assert TaskStatus.PENDING in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS], \
        "State matrix no longer allows IN_PROGRESS → PENDING"
    assert TaskStatus.BLOCKED in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS], \
        "State matrix no longer allows IN_PROGRESS → BLOCKED"

    threshold = datetime.now(UTC) - timedelta(minutes=timeout_minutes)

    # RT-7: Include tasks with NULL heartbeat (entered IN_PROGRESS via
    # transition_state instead of acquire_task)
    stmt = (
        select(Task)
        .where(
            Task.project_name == project_name,
            Task.status == TaskStatus.IN_PROGRESS,
            sqlalchemy.or_(
                Task.last_heartbeat_at < threshold,
                Task.last_heartbeat_at.is_(None),
            ),
        )
        .limit(batch_size)
    )
    result = await self.session.execute(stmt)
    zombies = result.scalars().all()

    # RT-11: Single timestamp for the entire batch (atomic operation semantics)
    now = datetime.now(UTC)
    # RT2-1: Collect zombie objects, serialize AFTER flush (not before)
    processed_zombies: list[tuple[Task, str]] = []  # (task, action)

    for zombie in zombies:
        # Increment attempt_count first to decide circuit breaker
        zombie.attempt_count += 1
        # RT-3: Increment version to signal state change to cached references
        zombie.version += 1

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

            # RT2-5: Use _build_defect for validation without flushing
            defect = self._build_defect(
                task_id=zombie.id,
                title=CIRCUIT_BREAKER_DEFECT_TITLE,
                description=(
                    f"Task {zombie.id} has failed {zombie.attempt_count} times. "
                    "Automatic circuit breaker activated."
                ),
            )
            self.session.add(defect)

            logger.error(
                "Circuit breaker activated: task_id=%s, attempt_count=%s, "
                "project=%s",
                zombie.id,
                zombie.attempt_count,
                project_name,
            )
            processed_zombies.append((zombie, "CIRCUIT_BREAKER"))
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
            processed_zombies.append((zombie, "RECYCLED"))

    # RT-9: Batch flush with error logging
    try:
        await self.session.flush()
    except Exception:
        zombie_ids = [str(z.id) for z, _ in processed_zombies]
        logger.error(
            "recycle_zombies batch flush failed for zombies: %s",
            zombie_ids,
        )
        raise

    # RT2-1: Serialize AFTER flush — return only persisted state
    return [
        {**self._task_to_dict(zombie), "resilience_action": action}
        for zombie, action in processed_zombies
    ]
```

> [!IMPORTANT]
> **`recycle_zombies` bypasses `transition_state` on purpose:**
> 1. `transition_state` increments `attempt_count` on ANY `BLOCKED` transition, but the circuit breaker needs to increment ONCE, then check. Reusing `transition_state` would double-increment.
> 2. `recycle_zombies` operates on a batch of tasks in a single flush. Calling `transition_state` per-task would cause N separate flushes.
> 3. The method still creates `StateTransition` records manually for the audit trail.

> [!CAUTION]
> **Bypass guard (RT-2):** `recycle_zombies` skips the `ALLOWED_TRANSITIONS` matrix check. The
> assertions at the top verify `IN_PROGRESS → PENDING` and `IN_PROGRESS → BLOCKED` are still legal;
> a matrix change fires them immediately. Unit test U-25 checks these matrix entries exist.

**3. `propagate_blocked(task_id: UUID) -> list[dict[str, object]]`** — cascades UPSTREAM_BLOCKED to
**all transitive upstream ancestors** via BFS (FR-9, AD-11, RT-4).

```python
async def propagate_blocked(self, task_id: uuid.UUID) -> list[dict[str, object]]:
    """Cascade UPSTREAM_BLOCKED to all transitive upstream ancestors (FR-9, AD-11).

    Uses BFS to traverse the full DAG upward from task_id, transitioning
    all eligible PENDING ancestors to UPSTREAM_BLOCKED (RT-4).

    Precondition: task_id must be in BLOCKED status (RT2-3).
    IN_PROGRESS parents are skipped with a warning (matrix disallows
    IN_PROGRESS → UPSTREAM_BLOCKED).

    Returns list of all affected ancestor task dicts.
    """
    # RT2-3: Precondition — verify source task is actually BLOCKED
    task = await self.session.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")
    if task.status != TaskStatus.BLOCKED:
        raise ValueError(
            f"Cannot propagate from task {task_id}: "
            f"status is {task.status.value}, expected BLOCKED"
        )

    affected: list[dict[str, object]] = []
    now = datetime.now(UTC)

    # RT-4: BFS traversal for all transitive ancestors
    queue: list[uuid.UUID] = [task_id]
    visited: set[uuid.UUID] = set()

    while queue:
        current_id = queue.pop(0)
        if current_id in visited:
            continue
        visited.add(current_id)

        # Find direct upstream parents of current_id
        stmt = (
            select(TaskDependency.parent_task_id)
            .where(TaskDependency.child_task_id == current_id)
        )
        result = await self.session.execute(stmt)
        parent_ids = [row[0] for row in result.fetchall()]

        for parent_id in parent_ids:
            if parent_id in visited:
                continue

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
            # RT3-1: Increment version to preserve OCC contract
            parent.version += 1

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

            # Continue BFS upward through this newly blocked parent
            queue.append(parent_id)

    await self.session.flush()
    return affected
```

The BFS visits every transitive ancestor reachable from `task_id` and moves eligible PENDING ones to
UPSTREAM_BLOCKED. Non-PENDING ancestors (DONE, ARCHIVED, IN_PROGRESS, already UPSTREAM_BLOCKED) are
skipped — they cannot transition or are already blocked. The `visited` set handles diamonds.

**4. `clear_upstream_blocked(task_id: UUID) -> list[dict[str, object]]`** — when a BLOCKED task is
unblocked, clears UPSTREAM_BLOCKED on **all transitive upstream ancestors** via BFS (FR-9, AD-11,
RT-4).

```python
async def clear_upstream_blocked(self, task_id: uuid.UUID) -> list[dict[str, object]]:
    """Reverse-propagate: clear UPSTREAM_BLOCKED on ancestors when blocker resolves (FR-9).

    Uses BFS to traverse the full DAG upward from task_id.
    Only clears an ancestor if ALL of its children are no longer BLOCKED or
    UPSTREAM_BLOCKED (the parent has no remaining blockers).

    Precondition (RT2-4): task_id should no longer be in BLOCKED/UPSTREAM_BLOCKED.
    If it is, returns early with a warning.

    Returns list of cleared ancestor task dicts.
    """
    # RT2-4: Precondition — verify the source task is no longer blocked
    task = await self.session.get(Task, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")
    if task.status in (TaskStatus.BLOCKED, TaskStatus.UPSTREAM_BLOCKED):
        logger.warning(
            "clear_upstream_blocked called but task %s is still %s",
            task_id, task.status.value,
        )
        return []

    cleared: list[dict[str, object]] = []
    now = datetime.now(UTC)

    # RT-4: BFS traversal for all transitive ancestors
    queue: list[uuid.UUID] = [task_id]
    visited: set[uuid.UUID] = set()

    while queue:
        current_id = queue.pop(0)
        if current_id in visited:
            continue
        visited.add(current_id)

        # Find direct upstream parents of current_id
        stmt = (
            select(TaskDependency.parent_task_id)
            .where(TaskDependency.child_task_id == current_id)
        )
        result = await self.session.execute(stmt)
        parent_ids = [row[0] for row in result.fetchall()]

        for parent_id in parent_ids:
            if parent_id in visited:
                continue

            parent = await self.session.get(Task, parent_id)
            if parent is None or parent.status != TaskStatus.UPSTREAM_BLOCKED:
                continue

            # RT3-3: Single query to check if ANY child of this parent is still blocked
            blocker_stmt = (
                select(Task.id)
                .join(TaskDependency, TaskDependency.child_task_id == Task.id)
                .where(
                    TaskDependency.parent_task_id == parent_id,
                    Task.status.in_([TaskStatus.BLOCKED, TaskStatus.UPSTREAM_BLOCKED]),
                )
                .limit(1)
            )
            blocker_result = await self.session.execute(blocker_stmt)
            if blocker_result.scalar_one_or_none() is not None:
                logger.debug(
                    "Parent %s still has blocked children, skipping clear",
                    parent_id,
                )
                continue

            parent.status = TaskStatus.PENDING
            parent.updated_at = now
            # RT3-1: Increment version to preserve OCC contract
            parent.version += 1

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

            # Continue BFS upward through this newly cleared parent
            queue.append(parent_id)

    await self.session.flush()
    return cleared
```

> [!IMPORTANT]
> **Invariant**: `clear_upstream_blocked` checks ALL children of each ancestor, not just the one that
> was unblocked, so a parent with several children is not unblocked early. The BFS continues upward
> through cleared parents for multi-level DAGs (RT-4).

**Guide** · `docs/dev_guides/agent_memory_state_tracking.md` — three new sections:

1. **5. Heartbeat Pulsing** — agents call `pulse_heartbeat(task_id, worker_id)` during long-running
   work to avoid zombie collection. Cadence: every 5 minutes. `worker_id` must match the assigned
   worker (RT-3).
2. **6. Zombie Recovery & Circuit Breaker** — the orchestrator calls `recycle_zombies` on a
   schedule. The 3-strike rule (`attempt_count >= 3` across ALL failure paths) and auto-defect
   creation. Returned dicts include the `resilience_action` key. How to manually unblock
   circuit-broken tasks. `handover_context` is preserved during recycling (RT2-2).
3. **7. DAG Propagation** — how `propagate_blocked` and `clear_upstream_blocked` work with BFS
   transitive traversal (RT-4), when the orchestrator calls them, and the preconditions (source must
   be BLOCKED / not-blocked respectively).

| File | Change |
|------|--------|
| `src/specweaver/workspace/memory/repository.py` | modified — add `recycle_zombies`, `pulse_heartbeat`, `propagate_blocked`, `clear_upstream_blocked` |
| `tests/unit/workspace/test_memory_repository.py` | modified — add SF-04 unit tests |
| `tests/integration/workspace/test_memory_integration.py` | modified — add SF-04 integration + E2E tests |
| `docs/dev_guides/agent_memory_state_tracking.md` | modified — add resilience sections |

Commit boundaries:

- **CB-1: Heartbeat + Zombie Recovery + Audit Hardening** — `repository.py`: `_build_defect`,
  `pulse_heartbeat`, `recycle_zombies` (incl. circuit breaker); `create_defect` refactored to use
  `_build_defect`. `test_memory_repository.py`: U-1 through U-11, U-22, U-23, U-25, U-26, U-27,
  U-28, U-31, U-32, U-34, U-35. `test_memory_integration.py`: INT-11, INT-12, E2E-7.
- **CB-2: DAG Propagation + Documentation** — `repository.py`: `propagate_blocked`,
  `clear_upstream_blocked` (BFS-based). `test_memory_repository.py`: U-12 through U-21, U-24, U-29,
  U-30, U-33, U-36, U-37. `test_memory_integration.py`: INT-13, INT-14, INT-15, E2E-6.
  `agent_memory_state_tracking.md`: sections 5, 6, 7.

## Tests

Unit — new class `TestMemoryRepositoryResilience` in `test_memory_repository.py`:

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
| U-9 | `test_recycle_zombies_circuit_breaker_audit_trail` | NFR-8 | `StateTransition` with `CIRCUIT_BREAKER` reason + `Defect` with title `CIRCUIT_BREAKER_DEFECT_TITLE` |
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
| U-25 | `test_recycle_zombies_matrix_assertions` | RT-2 | Verify `ALLOWED_TRANSITIONS` includes `IN_PROGRESS → PENDING` and `IN_PROGRESS → BLOCKED` |
| U-26 | `test_pulse_heartbeat_wrong_worker` | RT-3 | Calling `pulse_heartbeat` with wrong `worker_id` raises ValueError |
| U-27 | `test_recycle_zombies_null_heartbeat` | RT-7 | Task with `last_heartbeat_at IS NULL` is detected as zombie |
| U-28 | `test_recycle_zombies_mixed_batch` | RT-12 | Batch with 2 recyclable + 1 circuit-broken task → correct statuses per task |
| U-29 | `test_propagate_blocked_source_not_blocked` | RT2-3 | Calling `propagate_blocked` on a PENDING task raises ValueError |
| U-30 | `test_clear_upstream_blocked_source_still_blocked` | RT2-4 | Calling `clear_upstream_blocked` on a still-BLOCKED task returns empty with warning |
| U-31 | `test_recycle_zombies_resilience_action_key` | RT2-7 | Returned dicts contain `resilience_action` = `"RECYCLED"` or `"CIRCUIT_BREAKER"` |
| U-32 | `test_recycle_zombies_nonexistent_project` | RT2-10 | `recycle_zombies("nonexistent")` returns empty list, no error |
| U-33 | `test_propagate_blocked_parent_already_upstream_blocked` | RT2-11 | Parent already UPSTREAM_BLOCKED from a different child → skipped, no duplicate transition |
| U-34 | `test_recycle_zombies_zero_timeout` | RT2-12 | `timeout_minutes=0` recycles all IN_PROGRESS tasks with any heartbeat |
| U-35 | `test_recycle_zombies_batch_limit` | RT3-2 | `batch_size=2` only processes 2 out of 3 available zombies |
| U-36 | `test_propagate_blocked_increments_version` | RT3-1 | Parent OCC version increments when transitioning to UPSTREAM_BLOCKED |
| U-37 | `test_clear_upstream_blocked_increments_version` | RT3-1 | Parent OCC version increments when transitioning to PENDING |

Integration and E2E — `test_memory_integration.py`:

| # | Test Name | Category | Scenario |
|---|-----------|----------|----------|
| INT-11 | `test_int_11_zombie_reaper_full_cycle` | Integration | Create task → acquire → backdate heartbeat → recycle_zombies → verify PENDING + attempt_count=1 + version incremented → re-acquire → succeed |
| INT-12 | `test_int_12_circuit_breaker_three_strikes` | Integration | Task fails 3 times through recycle_zombies → circuit breaker fires → verify BLOCKED + Defect with `CIRCUIT_BREAKER_DEFECT_TITLE` + `resilience_action="CIRCUIT_BREAKER"` |
| INT-13 | `test_int_13_upstream_propagation_cascade` | Integration | Build A→B→C chain, block C → `propagate_blocked(C)` → BFS auto-cascades: B AND A both transition to UPSTREAM_BLOCKED in a single call |
| INT-14 | `test_int_14_reverse_propagation_partial` | Integration | A depends on B and C, B blocked → A UPSTREAM_BLOCKED → C unblocked but B still blocked → A stays UPSTREAM_BLOCKED |
| INT-15 | `test_int_15_reverse_propagation_full_clear` | Integration | Same as INT-14 but B also unblocks → `clear_upstream_blocked(B)` BFS clears A to PENDING |
| E2E-6 | `test_e2e_6_resilient_dag_execution` | E2E | Full lifecycle: Create Epic + 3 tasks in DAG → T1 completes → T2 zombies → circuit breaker fires → T3 UPSTREAM_BLOCKED via BFS → human resolves T2 defect → unblock → T3 resumes → Epic closes |
| E2E-7 | `test_e2e_7_heartbeat_survival` | E2E | Agent acquires task → pulses heartbeat with correct `worker_id` → zombie scan runs → task NOT recycled |


```bash
# Unit tests only (SF-04 tests)
pytest tests/unit/workspace/test_memory_repository.py -k "Resilience" -v

# Integration tests only (SF-04 scenarios)
pytest tests/integration/workspace/test_memory_integration.py -k "int_11 or int_12 or int_13 or int_14 or int_15 or e2e_6 or e2e_7" -v

# Full memory bank test suite
pytest tests/unit/workspace/test_memory_repository.py tests/integration/workspace/test_memory_integration.py -v

# Full project test suite (all 4600+ tests)
pytest

# Quality gates (RT2-13)
ruff check src/specweaver/workspace/memory/
ruff format --check src/specweaver/workspace/memory/
mypy src/specweaver/workspace/memory/repository.py --ignore-missing-imports
tach check
```

Manual: inspect the `StateTransition` audit trail after zombie recycling and propagation; check the
structured log format against NFR-8; review the guide sections; confirm the `sqlalchemy.or_` import
in repository.py (RT-7) and the `CIRCUIT_BREAKER_DEFECT_TITLE` module constant (RT2-5).

## Decisions (audit)

Three Red Team / Blue Team rounds:

- **Round 1**: 14 findings, 7 modifications accepted — `attempt_count` semantics (RT-1), defensive
  matrix assertions (RT-2), `worker_id` validation (RT-3), BFS propagation (RT-4), NULL heartbeat
  handling (RT-7).
- **Round 2**: 13 findings, 8 modifications accepted — post-flush serialization (RT2-1),
  `propagate_blocked` precondition (RT2-3), `_build_defect` extraction (RT2-5), `resilience_action`
  return key (RT2-7), research note contradiction fix (RT2-8).
- **Round 3**: 4 findings, 3 modifications accepted — version increment in propagation to keep the
  OCC contract (RT3-1), bounded batch size (RT3-2), one blocker query per parent instead of N+1 in
  reverse propagation (RT3-3).

**Cumulative**: 31 findings, 18 modifications, 13 additional tests (U-25–U-37), 5 findings rejected
as correct-by-design.

## As built

**Since moved** (`fde43dec`, 2026-05-07): the methods live in the package
`workspace/memory/repository/` — `recycle_zombies`, `propagate_blocked`, `clear_upstream_blocked` in
`resilience.py`; `pulse_heartbeat` in `core.py`; `CIRCUIT_BREAKER_DEFECT_TITLE` is defined in both
`core.py` and `resilience.py`. Unit tests are in `test_memory_repository_resilience.py`. Line refs
above are as of the plan's date.
