# Implementation Plan: Deep Semantic Hashing [SF-4: Pipeline Execution Optimization]
- **Feature ID**: 3.32
- **Sub-Feature**: SF-4 — Pipeline Execution Optimization
- **Design Document**: docs/roadmap/features/topic_02_sensors/A-SENS-01/A-SENS-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-4
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/A-SENS-01/A-SENS-01_sf4_implementation_plan.md
- **Status**: APPROVED

## Goal Description

Feature 3.32 SF-4 optimizes the execution pipeline by natively consuming the `stale_nodes` diff calculated by the Incremental Topology Crawler in SF-3. The orchestration engine (`QARunner`, `PipelineRunner`, and `EngineFileExecutor`) will be modified to bypass unmodified (clean) nodes, radically accelerating build and validation loop times. Finally, we will implement the explicit mathematical flush of the Semantic Cache ONLY when the pipeline successfully executes integration validations.

## User Review Required

> [!CAUTION]
> **Hitl Review Required for Cache-Flush Dilemma Execution**
> I am proposing that `DependencyHasher.save_cache()` is called strictly at the resolution of a successfully completed CI/Validation workflow loop. Placing this exactly within the `PipelineRunner` or the specific `QARunnerHandler` will ensure the cache refuses to update if tests fail, forcing the user to fix the stale nodes on subsequent loops. Please review the specific hook point in `runner.py`.

## Proposed Changes

---

### Architectural Boundaries (`context.yaml`)

> [!CAUTION]
> **Boundary Violation Remediation (Reverting Option C)**
> Modifying `src/specweaver/core/flow/context.yaml` to consume `specweaver/assurance/graph` would introduce a **violent architectural violation**. According to the strict L1–L6 module dependency graph (`architecture_reference.md`), `flow` and `graph` are siblings consumed exclusively by `cli` and `api`. They cannot consume each other!
> 
> Therefore, **Option C (Dedicated Handler in Flow)** and **Option A (PipelineRunner Hook)** are mathematically illegal because they force `flow` to import `DependencyHasher`.
> 
> **The Architecturally Pure Solution (Decoupled Injection):**
> 1. `flow` will NOT consume `graph`.
> 2. `TopologyGraph` and `DependencyHasher` will continue to operate natively inside `assurance/graph` without polluting the `flow` engine.
> 3. We will leverage `RunContext` and `CLI` bridging.

---

### CLI Orchestrator (`specweaver.cli`)

#### [x] [MODIFY] [cli/project_commands.py or CLI entrypoints]
- **Post-Validation Cache Flush**: Following the execution of `runner.run()`, the `CLI` (which mathematically possesses access to both `flow` and `graph`) will check if the Pipeline Run was perfectly successful. If so, it invokes `DependencyHasher.save_cache()`. This perfectly resolves the Cache-Flush Dilemma at the exact correct L1 layer!

---

### Core Flow Engine (`specweaver.core.flow.engine`)

#### [x] [MODIFY] [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/engine/runner.py)
- **Staleness Bypass Instruction**: Inject a check inside `_execute_loop` that reads `context.stale_nodes`. 
  - **Optimization**: If `step_def.target != StepTarget.PROJECT` and is not in `stale_nodes`, skip it instantly. 
  - **Optimization**: If `step_def.target == StepTarget.PROJECT`, do NOT skip the step. Instead, inject the `stale_nodes` deeply into the Step payload so the downstream atoms can rewrite physical sub-paths.
- **Engine Sandbox Symlinks**: Modify `setup_sandbox_caches` inside `runner_utils.py` to append `.specweaver` to the cache directory array, injecting the cache securely via `os.symlink`.

---

### Handlers & Plugins (`specweaver.core.loom`)

#### [x] [MODIFY] [qa_runner/atom.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/atoms/qa_runner/atom.py)
- **Target Rewriting Optimization**: In `_intent_run_tests`, `_intent_run_linter`, etc., check if `stale_nodes` is provided in the `context`. If the `target` parameter is global (e.g., `.`), automatically intercept and route multiple granular checks bounded strictly to the `stale_nodes` paths, aggregating the returns natively. This converts a 1-minute full scan into a <200ms delta scan!

#### [x] [MODIFY] [runner_utils.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/engine/runner_utils.py)
- **Deviation Note on executor.py**: Instead of executing directly on `executor.py` or falling back to raw `os.symlink` (which triggered an architectural violation in our gap analysis), we formally integrated `setup_sandbox_caches` to natively trigger `FileSystemAtom` with `intent: symlink`. This ensures path traversal boundaries remain perfectly secured.

## Open Questions

None. The architectural audit resolved the Cache-Flush dilemma by moving the responsibility up to the CLI orchestrator to ensure zero dependency violations between the Flow and Graph domains.

## Session Handoff for Developer Agent
Everything is fully resolved. When you start the `/dev` workflow, you have clear instructions to implement the Staleness check via `context.stale_nodes` inside `runner.py`, and you must implement the Cache-Flush hook via the exact `CLI` entrypoint that commands the pipeline. **DO NOT** modify `context.yaml` boundary configurations!

### Automated Tests
- Integration tests simulating a `clean` module bypass mechanism explicitly through the QARunner lifecycle.
- Integration test validating the `.specweaver` cache gets effectively symlinked and persists back.

### Manual Verification
- Will trigger a full pipeline execution natively hitting the `QARunner`, observing the CLI output state reporting a successful `Bypass` due to pristine hashes.
