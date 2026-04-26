# Implementation Plan: Common MCP Client Architecture [SF-1: Context YAML & Vault Bindings]

- **Feature ID**: 3.32c
- **Sub-Feature**: SF-1 — Context YAML & Vault Bindings
- **Design Document**: docs/roadmap/features/topic_04_intelligence/C-INTL-02/C-INTL-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/C-INTL-02/C-INTL-02_sf1_implementation_plan.md
- **Status**: COMPLETED

## 1. Goal Description

This sub-feature integrates the Model Context Protocol (MCP) server definitions directly into the DAG-based `context.yaml` boundaries and guarantees that environment bindings (.specweaver/vault.env) never leak credentials to the repository or internal logging. It adapts the `TopologyNode` model for parsing and natively integrates the security Git tracking check Option D.

> [!IMPORTANT]
> **Architectural Fix Applied**: `context.yaml` is NOT validated via Pydantic; it maps to `TopologyNode` via `ruamel.yaml`. The schema expansion bypasses Pydantic entirely to prevent L2 Graph regression. Pydantic validation migrations have been deferred to `Feature 3.32d`.

> [!CAUTION]
> **Architectural Safety (The Option D Vault Shield):** To prevent breaking the `pure-logic` isolation rule of the configuration layer, we cannot run arbitrary `subprocess-git` checks from `core/config/`. The Git tracking check MUST be orchestrated securely through the `flow` PipelineRunner invoking `GitAtom` natively. 

---

## 2. Proposed Changes

### specweaver/assurance/graph/
#### [MODIFY] `src/specweaver/assurance/graph/topology.py`
- Modify the `TopologyNode` dataclass to explicitly accept:
  - `mcp_servers: dict[str, dict] = field(default_factory=dict)`
  - `consumes_resources: list[str] = field(default_factory=list)`
- Update `TopologyGraph.from_project()` loader block to pull these directly from the `ruamel.yaml` dictionary mapping.

### specweaver/core/flow/
#### [MODIFY] `src/specweaver/core/flow/engine/runner.py`
- Modify `PipelineRunner.start()` or initialization sequence.
- **Implement Option D Vault Verification**:
  1. Instantiate the `FileSystemAtom` to check if `Path(".specweaver/vault.env").exists()`.
  2. If it exists, instantly execute `GitAtom.run(command="ls-files .specweaver/vault.env")`.
  3. If the GitAtom returns a stdout hit (indicating the file is currently tracked), violently throw a fatal `RuntimeError("FATAL: vault.env is currently tracked by Git! Aborting execution to prevent credential leakage.")`.
- By using `.exists()` early-exit, the performance overhead is ~0ms for projects that don't utilize MCP, effectively eliminating any boot-time regressions while maximizing enterprise-grade security.

---

## 3. Phase 5 Consistency Verification Answers

5.1. **Open questions:** Are there still any unresolved decisions or ambiguities?
- **No**. The Pydantic discrepancy is resolved (deferred). The Option D credential vulnerability is locked. The LLM won't be guessing about parsing. All bounds are explicitly defined.

5.1a. **Agent Handoff Risk**: A fresh agent will NOT struggle. The exact files to modify and the exact APIs (`TopologyNode`, `GitAtom`, `PipelineRunner`) are explicitly listed. There are zero implicit imports assumed.

5.2. **Architecture and future compatibility:** 
- The plan perfectly complies with `context.yaml` isolation. By refusing to write `subprocess` logic inside configuration, we prevent `tach` from failing the topological DAG compliance check. Running side-effects requires `Atoms`, and `PipelineRunner` natively possesses the clearance to orchestrate them.

5.3. **Internal consistency:** 
- `[MODIFY]` tags reflect exact correct file paths. All changes stay firmly within Phase 3 scope paths.

---

## 4. Verification Plan

### Automated Tests
- Run `pytest tests/unit/assurance/graph/test_topology.py` to ensure legacy context files (without `mcp_servers`) do not throw `KeyErrors`.
- Run `pytest tests/unit/core/flow/engine/test_runner.py` with mock `.specweaver/vault.env` files to confirm the `GitAtom` forcibly aborts the pipeline when the mock returns a tracked file status.

### Manual Verification
- Execute `sw plan` across a test repo containing `.specweaver/vault.env` that has been explicitly `git add`ed. Pipeline must exit immediately.
