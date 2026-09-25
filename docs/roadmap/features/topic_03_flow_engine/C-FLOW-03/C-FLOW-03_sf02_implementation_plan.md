# C-FLOW-03 SF-02 — Sandbox Environmental Isolation

**Status**: DONE · **FRs owned**: FR-2 — the RESERVE gate's atomic reservation (recorded 2026-08-17
under `specweaver-dev` §3.2c, from `INT-US-18-MIG`) · **Depends on**: SF-01 · Design:
[C-FLOW-03_design.md](C-FLOW-03_design.md) §Sub-Feature Breakdown → SF-02 · Feature ID 3.27

Proof and mutant: `tests/unit/core/flow/engine/test_runner_gates.py` — skipping `evaluate_reserve`
fails it.

## Goal

Concurrent, overlapping multi-spec agents avoid lock bugs without halting the orchestrator event
loop: serialized `git worktree` setup, and SQL/environment isolation per sub-pipeline.

## Changes

1. **[MODIFY] `src/specweaver/core/flow/_base.py`** — `RunContext`:
   - `env_vars: dict[str, str] | None = Field(default_factory=dict)`, per sub-pipeline, so each
     sandboxed run controls its own network/DB footprint.
   - accepts `context.pipeline_name`, so `runner.py` can build deterministic, readable branch names.
2. **[MODIFY] `src/specweaver/core/flow/state.py`** — `GateType` gains `RESERVE` beside `AUTO`,
   `HITL` and `JOIN`; the evaluation pipeline routes it.
3. **[NEW] `src/specweaver/core/flow/reservation.py`** — `SQLiteReservationSystem`, an atomic lock
   in SQLite:
   - table: `CREATE TABLE IF NOT EXISTS sw_reservations (resource_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, expires_at DATETIME)`
   - `.acquire(resource_id, run_id)`: `try: INSERT ... except sqlite3.IntegrityError: return False`,
     logging `Race condition lost naturally by <run_id> for lock <resource_id>`.
   - `.release(resource_id, run_id)` deletes the lock.
4. **[MODIFY] `src/specweaver/core/flow/runner.py`**
   - **Environment:** inject the parent's `.env_vars` into LLM calls and shell executables spawned
     under `_execute_loop`.
   - **Branch names:** `branch = f"sf-{clean_pipeline}-{task_id}"`, sanitized with `.replace(' ', '_')`.
   - **Cleanup:** a `finally:` block runs the DB `.release`, so a crashed sub-shell never leaves a
     zombie lock.
5. **[MODIFY] `src/specweaver/core/flow/gates.py`** — `evaluate_reserve()`: if
   `SQLiteReservationSystem.acquire(...)` fails (unique-constraint block), log
   `[run_id=X] Sandbox environment reservation for {resource_id} is locked by another agent. Yielding verdict=PARK`
   and return `verdict="park"` to `_execute_loop`. The parent DAG dispatcher polls and `resumes`
   parked runs.

> [!CAUTION]
> Ensure all DB calls for `sw_reservations` aggressively wrap `sqlite3` driver errors specifically to avoid breaking the core flow event loop when an overlapping test starts.

Deferred to SF-03: LLM rate throttling (`asyncio.Semaphore()`) and global documentation synthesis
(`GateType.JOIN`).

## Decisions (HITL)

| Topic | Chosen | Why |
|---|---|---|
| Worktree naming | `Pipeline + Task ID` (Option C), over static components and UUIDs | No lock collisions; readable when debugging |
| Reservation | `GateType.RESERVE` gate over an atomic SQLite unique constraint (`IntegrityError`) (Option C) | No sleep-and-retry loops in Python; collisions are logged |
| SW_PORT_OFFSET variables | explicit `RunContext.env_vars` inside the PipelineRunner, not global overrides (Option A) | Isolation per sub-pipeline |

## As built

- `[x]` Dev Implementation.
- `[x]` Full Quality Gate passed.

Verified 2026-09-25: `SQLiteReservationSystem` and `sw_reservations` exist
(`core/flow/engine/reservation.py`), and the branch format is in `core/flow/engine/sandboxed_execution.py`.
`env_vars` and `SW_PORT_OFFSET` do not exist in `src/`; with serialized worktree creation they are
the deleted FR-3/FR-4, now `TECH-062`.
