# Agent Memory State Tracking

This guide details how to correctly interact with the `MemoryRepository` for task execution, handling state transitions, and managing Optimistic Concurrency Control (OCC) when building SpecWeaver agents.

## Core Concepts

The **Agent Memory Bank** (US-28) provides a resilient, local SQLite-backed ledger for agent tasks. Instead of relying on volatile RAM arrays or raw `networkx` graphs, agents coordinate work through a strictly controlled state machine.

### 1. Task Acquisition (Optimistic Concurrency Control)

Agents do not directly update the database with `session.execute("UPDATE...")`. Instead, they must call `acquire_task`. 

Because multiple agents (or Orchestrator background scripts) might try to acquire the same pending task simultaneously, SpecWeaver uses **Optimistic Concurrency Control (OCC)** based on a `version` column.

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

**Rule:** Always catch `StaleTaskVersionError`. Do not crash the agent pipeline on OCC collisions. The `MemoryRepository` will emit a `logger.warning()` automatically.

### 2. State Transitions & The Matrix

The memory bank enforces a strict State Transition Matrix. You cannot jump directly from `DONE` back to `PENDING` without a valid path. 

To transition a task, use `repo.transition_state()` with the corresponding `TransitionReason` enum.

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

**Defect Invariants:** The system will physically block the transition to `DONE` if there are any `OPEN` defects associated with the task, throwing a `DefectBlocksCompletionError`.

### 3. Context Handover Limits

When an agent needs to hand over work or store intermediate context, they update the `handover_context`. This is strictly limited to prevent LLM prompt token overflow.

```python
from specweaver.workspace.memory.models import HandoverContext

context = HandoverContext(
    summary="I have implemented the database schema but need the API route.",
    stack_trace="Exception: Route not found...",
    metadata={"files_touched": ["store.py"]}
)

await repo.update_handover_context(task_id, context)
```

**Rules:**
1. Pydantic enforces an absolute **8KB** physical size limit on the serialized JSON payload.
2. The `stack_trace` string is automatically truncated to the last 2000 characters.
3. The `metadata` dictionary only accepts primitive types (`str`, `int`, `float`, `bool`) or lists of primitives. No deeply nested, hallucinated JSON structures are allowed.

### 4. DAG Cycle Protection

When building topologies dynamically, use `insert_dependency`. The repository runs a `WITH RECURSIVE` SQLite CTE to protect the Flow Engine from infinite loop hallucinations.

```python
from specweaver.workspace.memory.errors import CyclicDependencyError

try:
    await repo.insert_dependency(parent_id, child_id)
except CyclicDependencyError:
    print("Agent attempted to create an infinite dependency loop!")
```

### 5. Heartbeat Pulsing

To prevent "zombie" tasks from permanently holding locks, the agent must periodically ping the repository. Only tasks in the `IN_PROGRESS` state can be pulsed, and only by the assigned worker.

```python
# The worker loop must periodically await this while executing long-running tasks
updated_task = await repo.pulse_heartbeat(task_id, worker_id="agent-uuid")
```

### 6. Zombie Recovery & Circuit Breaker

The system relies on an Orchestrator-level script to periodically clean up zombies. If a task fails repeatedly (e.g., due to an unrecoverable LLM hallucination or crash), a Circuit Breaker activates to prevent infinite loops.

```python
# Typically runs every 5 minutes in a background task
recycled = await repo.recycle_zombies(project_name="my-project", timeout_minutes=15)

for action in recycled:
    if action["resilience_action"] == "CIRCUIT_BREAKER":
        print(f"Task {action['id']} failed 3+ times. It is now BLOCKED and requires human intervention.")
    else:
        print(f"Task {action['id']} died. Reset to PENDING for re-acquisition.")
```

**Note on Circuit Breakers**: When a circuit breaker triggers, the system automatically creates a `Defect` on the task. The task cannot transition to `DONE` until this defect is manually marked as `RESOLVED` by a developer.

### 7. DAG Propagation

When a task becomes `BLOCKED` (e.g. by a circuit breaker or manual agent failure), the orchestrator must flag all tasks that depend on it so they don't start executing. SpecWeaver does this automatically via Breadth-First Search (BFS) DAG traversal.

```python
# When a task blocks, cascade UPSTREAM_BLOCKED to all PENDING ancestors
affected_ancestors = await repo.propagate_blocked(task_id=task.id)

# When the task is unblocked (e.g., defect resolved), clear UPSTREAM_BLOCKED 
# from all ancestors, resetting them to PENDING (if they have no other blockers)
cleared_ancestors = await repo.clear_upstream_blocked(task_id=task.id)
```

**Precondition Requirements**: `propagate_blocked` expects the source task to be `BLOCKED`. `clear_upstream_blocked` expects the source task to be unblocked (e.g., `PENDING` or `IN_PROGRESS`). If called incorrectly, they will raise an error or log a warning and return an empty list.

### 8. Context Hydration & Handover Formatting

While `MemoryRepository` handles the write-side state machine, the read-side context injection is fully autonomous and managed by the `MemoryHydrator`.

Agents do not need to manually query the memory bank when starting work. Instead:
1. The `_build_base_prompt()` function automatically calls `MemoryHydrator.hydrate()` for the active project.
2. The Hydrator fetches `IN_PROGRESS` and `BLOCKED` tasks, plus recently `DONE` tasks that contain a `handover_context`.
3. The context is automatically strictly formatted as JSON, wrapped in an `<agent_memory trust="low">` XML block to prevent prompt injection, and injected into the LLM context window with a hard limit of **2048 tokens**.

If an agent needs to pass knowledge to the next agent, they simply update the `handover_context` before transitioning the task. The Hydrator will automatically ensure the next agent sees it (subject to priority truncation rules if the token budget is exhausted).

### Example: Handler-Based Prompt Assembly (IoC)

SpecWeaver utilizes Inversion of Control to build the prompt. The base prompt, including the memory block, is constructed in the Application layer, completely isolating the domain workflows from `MemoryHydrator`.

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
