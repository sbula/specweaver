# Design: Multi-spec pipeline fan-out

- **Feature ID**: 3.27
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3.27/feature_3.27_design.md

## Feature Overview

Feature 3.27 adds multi-spec pipeline fan-out capabilities to the PipelineRunner.
It solves the problem of serial execution bottleneck for disjoint components by spawning separate L3 pipelines for each component outputted by decomposition, running them fully in parallel.
It interacts with the Topology Graph (to mathematically predict and enforce disjoint file blast radiuses) and the Git Worktree Bouncer (to isolate execution in separate sandboxes), while injecting offset hashes (`SW_PORT_OFFSET`) to prevent test side effects like port and DB locking, and does NOT touch components with overlapping blast radiuses (these must be handled safely or serialized).
Key constraints: Must use Topology Graph for blast radius prediction, must run disjoint components fully in parallel within isolated separate sandboxes, must inject `SW_PORT_OFFSET` to avoid port/SQLite collisions, and must completely avoid git merge conflicts.

## Research Findings

### Codebase Patterns
- **`PipelineRunner.fan_out(sub_pipelines, ...)`** already exists, and uses `asyncio.gather()` to run multiple pipelines concurrently.
- **`OrchestrateComponentsHandler`** extracts decomposition components and currently triggers `fan_out` blindly.
- **Git Worktree Bouncer** natively isolates filesystem context using the `use_worktree` flag on steps (via `GitAtom`).
- **`TopologyGraph`** exposes robust dependency queries (`impact_of()`, `dependencies_of()`) allowing mathematically verifiable predictions of overlapping file blast radiuses.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Git | ^2.30.0 | git worktree | Host Environment |
| Python asyncio | ^3.10 | asyncio.gather | Host Environment |

### Blueprint References
- Archon: Deterministic Collision Routing → Assigning deterministic hash-based port offsets to temporary git worktree sandboxes, avoiding OS resource collisions (`EADDRINUSE` or SQLite locking) during parallel test execution.
- DMZ Ecosystem: Strict isolation principles separating executing worker agents from shared integration/documentation steps.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Blast Radius Wave Scheduling | Orchestrator | Analyzes each decomposed component against the `TopologyGraph` and explicitly enforces `depends_on` logical dependencies. | Identifies completely disjoint sets of components and assigns them to sequential execution "Waves" (DAG). |
| FR-2 | Resource Reservation Locking | PipelineRunner | Checks an SQLite Reservation Table before spawning worktrees. | Cross-feature multi-agent collisions are gracefully parked if modules or ports intersect. |
| FR-3 | Dynamic Port Offset Injection | PipelineRunner | Injects a unique `SW_PORT_OFFSET` hash into the environment of a sandbox worktree. | Testing instances and mock servers do not collide on network ports or SQLite database locks. |
| FR-4 | Serialized Worktree Context Prep | Orchestrator | Pauses background GC (`gc.auto 0`) and sequentially creates `.worktree` directories and unique branches per component. | Avoids fatal Git locking collisions natively experienced when spawning parallel Git worktree tasks. |
| FR-5 | Deferred Artifact Synthesis | Orchestrator | Delays generation of shared documentation (`README.md`, `context.yaml`) until after parallel execution. | Implements a `GateType.JOIN` ensuring shared artifacts are merged safely without collision. |
| FR-6 | DAG Cascading Failures | PipelineRunner | Monitors wave batch execution states and aborts downstream dependents. | If Component A fails in Wave 1, Component B (which conceptually `depends_on` A) is safely aborted in Wave 2. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Git Merge Safety | 100% guarantee that parallel sandboxes will not incur git merge conflicts. Achieved strictly by ensuring disjoint topological scopes. |
| NFR-2 | Infrastructure Isolation | Package dependency updates (e.g. `pyproject.toml`) strictly serialize into a `Wave 0` infrastructure layer to prevent lock hash merge collisions entirely. |
| NFR-3 | Rate Limit Resiliency | Must throttle LLM concurrent API calls natively with `asyncio.Semaphore()` bound to Provider configurations to stop HTTP 429 crash loops. |
| NFR-4 | Log Observability | Parallel pipeline log streams must be strictly tagged by `run_id` to ensure humans can debug asynchronous failures without chaotic console interleaving. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Git | 2.30.0 | git worktree add | Yes | Already integrated in 3.26 |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Static Wave Scheduling (DAG) via TopologyGraph | Deterministic Wave generation guarantees collision-free sub-branches across the parallel execution grid without introducing deadlock hazards found in Dynamic Module Mutex locks. | No |
| AD-2 | Deferred Documentation JOIN Gate | Isolating executed code flows from aggregate shared reporting artifact updates (`README.md`, `context.yaml`) avoids massive markdown collisions. | No |
| AD-3 | Component-Unique Branch Names | Directly overriding generic `sf-temp` branch names with unique component appended namespaces automatically intercepts Git Branch Exclusivity errors without UUID generation overhead. | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Multi-Agent Scaling Guide | Detail how topology constraints affect L3 component generation and speed processing constraints. | ⬜ To be written during Pre-commit |

## Edge Cases Handled

1. **DAG Cycle (Circular Dependencies)**: If the LLM generates a Decomposition Plan where Component A depends on B, and B depends on A, the `OrchestrateComponentsHandler` will mathematically detect the cycle and **fail fast** before any pipelines boot, rather than causing an infinite lock.
2. **Orphaned SQLite Locks (SIGKILL)**: If the main daemon is hard-killed (e.g., OOM exception or user hits Ctrl-C), the SQLite Resource Lock might be orphaned. The locking schema checks the parent process PID; if the PID is dead, the stale lock is safely ignored by new jobs.
3. **Graceful Parallel Degradation**: If 5 components are detected to all touch the exact same module (i.e. 100% collision), the Wave Generator dynamically degrades to purely serial execution (Wave 1, Wave 2 ... Wave 5) to guarantee safety, rather than failing altogether.
4. **Straggler Tasks**: If 4 tasks in a wave finish quickly but 1 stalls infinitely, the entire DAG stalls. To prevent this, standard pipeline timeouts apply forcefully to the `asyncio` envelope, marking the straggler as FAILED and allowing downstream aborts (FR-6) to trigger immediately.
5. **Disk Exhaustion from Crashed Worktrees**: If a task fails spectacularly, a `finally` block strictly executes `git worktree remove --force`, guaranteeing that temporary sandboxes do not accumulate and fill the developer's hard drive.

## Sub-Feature Breakdown

### SF-1: Topological DAG Wave Generation
- **Scope**: Upgrades `DecompositionPlan` JSON schema to demand explicit `depends_on` nodes and target modules. Implements `TopologyGraph` collision detection logic within the Orchestration layer to classify components into mutually exclusive operational subsets (Waves).
- **FRs**: [FR-1, FR-6]
- **Inputs**: DecompositionPlan (Component JSON outputs), TopologyGraph.
- **Outputs**: Computationally filtered batches of PipelineDefinitions ready for safe `fan_out`.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3.27/feature_3.27_sf1_implementation_plan.md

### SF-2: Sandbox Environmental Isolation
- **Scope**: Modifies `PipelineRunner._execute_loop` and `RunContext` to accept env-var propagation (like `SW_PORT_OFFSET`), introduces strict serialized `git worktree add` loops to prevent index locking crashes, and implements SQLite Resource Reservation logic.
- **FRs**: [FR-2, FR-3, FR-4]
- **Inputs**: RunContext hash hints, `use_worktree` context.
- **Outputs**: Environment variables exposed correctly into spawned executor sub-shells, parked overlapping sessions gracefully.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/phase_3/feature_3.27/feature_3.27_sf2_implementation_plan.md

### SF-3: Parallel Engine Hardening
- **Scope**: Embeds LLM-Provider bound `asyncio.Semaphore` throttling, extracts shared file (Documentation/Lock files) modifications securely into deferred `GateType.JOIN` or sequential `Wave 0` steps.
- **FRs**: [FR-5]
- **Inputs**: Package generation steps, pipeline configurations.
- **Outputs**: Resilient orchestrator logic free of HTTP 429 timeouts and `.lock` file conflicts.
- **Depends on**: SF-2
- **Impl Plan**: docs/roadmap/phase_3/feature_3.27/feature_3.27_sf3_implementation_plan.md

## Execution Order

1. SF-1 (No deps - start immediately)
2. SF-2 (Depends on SF-1)
3. SF-3 (Depends on SF-2)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Topological DAG Wave Generation | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-2 | Sandbox Environmental Isolation | SF-1 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-3 | Parallel Engine Hardening | SF-2 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Feature Complete — Ready for Sub-Feature Planning.
**Next step**: Run `/implementation-plan docs/roadmap/phase_3/feature_3.27/feature_3.27_design.md SF-1`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
