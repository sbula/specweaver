# US-28: Agent-Native Issue & State Tracker - Integration Contracts

## Base Story Contract (`INT-US-28`)
* **Status:** ✅ Complete
* **Integration Description:** The Agent Memory Bank (`B-INTL-09`) provides persistent SQLite-backed schema (Task, Epic, DAG, StateTransition, Defect) with CRUD operations, a formal state machine, OCC concurrency, circuit breakers, zombie recovery, and upstream DAG propagation. The Context Hydration & Handover Engine (`D-INTL-06`) provides the read-side retrieval, prompt formatting (trust-tagged XML with 8KB payload limits), and fail-safe handover protocols (save on pipeline completion, bootstrap on hydration). Together they enable AI agents to seamlessly store session state, hand over complex tasks, and prevent context degradation across multi-step workflows.
* **Integration Seams:**
    * **B-INTL-09 → D-INTL-06:** The `handover_context` JSON column on `Task` is the shared integration surface. B-INTL-09 owns write-side validation (Pydantic schema, 8KB limit, truncation on ARCHIVED). D-INTL-06 owns read-side retrieval, formatting, and prompt injection.
    * **D-INTL-06 → core.flow:** `_build_base_prompt()` in `core.flow.handlers.base` internally calls `MemoryHydrator` to inject memory context into every LLM prompt. `save_handover_context()` in `core.flow.engine.handover` persists pipeline telemetry to the Memory Bank in the runner's `finally` block.
    * **Boundary Compliance:** `core.flow` consumes `workspace.memory` via `core/flow/context.yaml`. Verified clean by `tach check`.
* **Verifiable Proof:**
    * `tests/integration/workspace/test_memory_integration.py` — 20 integration tests covering the full B-INTL-09 lifecycle (OCC races, DAG cycles, zombie recovery, circuit breakers, upstream propagation, heartbeat storms, diamond DAGs).
    * `tests/integration/workspace/test_memory_hydration_flow.py` — E2E hydration flow from SQLite through MemoryHydrator to formatted XML output.
    * `tests/integration/core/flow/handlers/test_prompt_hydration.py` — Integration tests proving `_build_base_prompt` → `MemoryHydrator` → `MemoryRepository` → SQLite round-trip (populated + corrupted fallback).
    * `tests/integration/core/flow/engine/test_handover_persistence.py` — Integration tests proving pipeline telemetry persistence through `save_handover_context` → `MemoryRepository` → SQLite.
    * `tests/unit/workspace/test_memory_hydrator.py` — Unit tests for sanitization, trust tagging, truncation, and prompt formatting.
    * `tests/unit/workspace/test_bootstrap_protocol.py` — Unit tests for FR-9 bootstrap scenario verification.
    * `tests/unit/core/flow/engine/test_handover.py` — Unit tests for telemetry collection and fail-safe behavior.
    * `tests/unit/core/flow/engine/test_runner_handover.py` — Unit tests for PipelineRunner handover wiring.
    * `tests/unit/core/flow/handlers/test_build_base_prompt.py` — Unit tests for prompt assembly with memory context injection.

## Sub-Story Add-Ons

### Advanced Multi-Agent Concurrency (`INT-US-28-SUB`)
* **Status:** ⬜ Pending
* **Integration Description:** Advanced Row-Level Task Locking (Pessimistic Locks, WAL2, Deadlock Detection) for true multi-agent concurrent execution. Currently mitigated by OCC with exponential backoff (AD-6, AD-14 in B-INTL-09).
* **Verifiable Proof:** [Pending]
