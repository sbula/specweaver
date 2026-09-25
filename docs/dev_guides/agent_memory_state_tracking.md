# Agent Memory State Tracking

Use when: a SpecWeaver agent reads or writes tasks in the Agent Memory Bank (US-28) through `MemoryRepository`.

The memory bank is a local SQLite ledger of agent tasks behind a state machine. Agents coordinate
through it, not through RAM arrays or raw `networkx` graphs.

## Rules

1. Never write the tables directly (`session.execute("UPDATE...")`). Call `acquire_task`.
2. Always catch `StaleTaskVersionError`. An OCC collision must not crash the pipeline;
   `MemoryRepository` already emits a `logger.warning()`.
3. Change state only through `repo.transition_state()` with a `TransitionReason`. The State
   Transition Matrix rejects invalid paths (e.g. `DONE` straight back to `PENDING`).
4. `DONE` is blocked while the task has any `OPEN` defect: `DefectBlocksCompletionError`.
5. Handlers do not call `save_handover_context`. The `PipelineRunner` saves it (see Handover save).

## 1. Acquire a task (Optimistic Concurrency Control)

Several agents or Orchestrator background scripts may race for the same pending task. OCC on a
`version` column decides the winner.

```python
from specweaver.workspace.memory.store import MemoryRepository
from specweaver.workspace.memory.errors import StaleTaskVersionError

async def worker_loop(repo: MemoryRepository, worker_id: str, task_id: uuid.UUID):
    try:
        # Atomic lock: checks version, transitions to IN_PROGRESS, increments version
        task = await repo.acquire_task(task_id, worker_id)
        print(f"Task acquired successfully! Current version: {task['version']}")
        
    except StaleTaskVersionError as e:
        # Another agent beat us to the lock!
        # Do NOT panic. Implement exponential backoff and retry, or pick another task.
        print(f"OCC Collision: {e}")
```

## 2. Transition state

```python
from specweaver.workspace.memory.store import TaskStatus, TransitionReason

# Successfully completing work
await repo.transition_state(
    task_id=task_id,
    to_status=TaskStatus.DONE,
    reason=TransitionReason.COMPLETED
)

# Giving up on work due to an error
await repo.transition_state(
    task_id=task_id,
    to_status=TaskStatus.BLOCKED,
    reason=TransitionReason.AGENT_FAILURE
)
```

## 3. Hand over context

`handover_context` carries work or intermediate context to the next agent. It is capped so it
cannot overflow the prompt.

```python
from specweaver.workspace.memory.models import HandoverContext

context = HandoverContext(
    summary="I have implemented the database schema but need the API route.",
    stack_trace="Exception: Route not found...",
    metadata={"files_touched": ["store.py"]}
)

await repo.update_handover_context(task_id, context)
```

| Limit | Value |
|---|---|
| Serialized JSON payload | **8KB**, enforced by Pydantic |
| `stack_trace` | truncated to the last 2000 characters |
| `metadata` values | primitives (`str`, `int`, `float`, `bool`) or lists of primitives; no nesting |

## 4. Add dependencies (cycle protection)

`insert_dependency` runs a `WITH RECURSIVE` SQLite CTE and rejects cycles, so the Flow Engine never
gets an infinite loop.

```python
from specweaver.workspace.memory.errors import CyclicDependencyError

try:
    await repo.insert_dependency(parent_id, child_id)
except CyclicDependencyError:
    print("Agent attempted to create an infinite dependency loop!")
```

## 5. Pulse the heartbeat

A long-running agent pulses so its task is not treated as a zombie. Only `IN_PROGRESS` tasks can be
pulsed, and only by the assigned worker.

```python
# The worker loop must periodically await this while executing long-running tasks
updated_task = await repo.pulse_heartbeat(task_id, worker_id="agent-uuid")
```

## 6. Zombie recovery and circuit breaker

An Orchestrator-level script recycles zombies. A task that keeps failing trips the circuit breaker
instead of looping forever.

```python
# Typically runs every 5 minutes in a background task
recycled = await repo.recycle_zombies(project_name="my-project", timeout_minutes=15)

for action in recycled:
    if action["resilience_action"] == "CIRCUIT_BREAKER":
        print(f"Task {action['id']} failed 3+ times. It is now BLOCKED and requires human intervention.")
    else:
        print(f"Task {action['id']} died. Reset to PENDING for re-acquisition.")
```

A tripped breaker creates a `Defect` on the task. The task cannot reach `DONE` until a developer
marks the defect `RESOLVED`.

## 7. Propagate blocks through the DAG

When a task becomes `BLOCKED` (circuit breaker or agent failure), its dependents must not start.
A Breadth-First Search (BFS) over the DAG flags them.

```python
# When a task blocks, cascade UPSTREAM_BLOCKED to all PENDING ancestors
affected_ancestors = await repo.propagate_blocked(task_id=task.id)

# When the task is unblocked (e.g., defect resolved), clear UPSTREAM_BLOCKED 
# from all ancestors, resetting them to PENDING (if they have no other blockers)
cleared_ancestors = await repo.clear_upstream_blocked(task_id=task.id)
```

Preconditions: `propagate_blocked` needs the source task `BLOCKED`; `clear_upstream_blocked` needs
it unblocked (e.g. `PENDING` or `IN_PROGRESS`). Called wrongly, they raise, or log a warning and
return an empty list.

## 8. Read side: hydration

`MemoryRepository` is the write side. `MemoryHydrator` injects memory into prompts; agents do not
query the bank themselves.

1. `_build_base_prompt()` calls `MemoryHydrator.hydrate()` for the active project.
2. The Hydrator fetches `IN_PROGRESS` and `BLOCKED` tasks, plus recently `DONE` tasks that have a
   `handover_context`.
3. It formats them as JSON inside an `<agent_memory trust="low">` XML block (prompt-injection guard),
   capped at **2048 tokens**. Over budget, priority truncation applies.

To pass knowledge on, update `handover_context` before transitioning the task.

The base prompt, memory block included, is built in the Application layer (Inversion of Control, IoC),
so domain workflows never see `MemoryHydrator`:

```python
# In src/specweaver/core/flow/handlers/your_handler.py
from specweaver.core.flow.handlers.base import _build_base_prompt

async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
    # 1. Build the base prompt (instructions, rules, metadata, AND Agent Memory)
    # The hydration is fail-safe; if DB fails, it gracefully omits memory.
    base_prompt = await _build_base_prompt(
        context,
        instructions="You are an expert developer...",
        include_rules=True 
    )

    # 2. Add domain-specific blocks
    if context.topology:
        base_prompt.add_topology([context.topology])

    # 3. Pass the pre-assembled prompt down to the isolated workflow
    result = await generator.generate_code(
        spec_path,
        output_path,
        base_prompt=base_prompt
    )
```

## 9. Handover save (pipeline interception)

When a pipeline completes, fails, or is interrupted, `PipelineRunner` runs a fail-safe telemetry
sweep:

1. **Scrape step records**: `files_touched` from successful outputs, `error_message` strings from
   failures.
2. **Sanitize**: deduplicate errors; keep at most 10 errors (each truncated to 500 chars) and 30
   files, so the JSON fits the 8KB budget.
3. **Persist**: find the project's active `IN_PROGRESS` task and commit the `HandoverContext` to
   SQLite.

The next agent gets the telemetry even if this one died on a `KeyboardInterrupt` or an unhandled LLM
exception.
