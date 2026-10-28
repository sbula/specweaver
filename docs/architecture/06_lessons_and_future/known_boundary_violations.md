# Known Boundary Violations

The live ledger of module-boundary violations that could not be fixed inside the feature that
found them. Rule (`specweaver-pre-commit` Phase 1.8): fix a violation in scope, or add a row here
with what, where, and which rule is broken. None may be skipped silently.

## Open and recently resolved

| Violation | Where | Rule Broken | Status |
|-----------|-------|-------------|--------|
| `File I/O` inside `pure-logic` | `src/specweaver/assurance/graph/hasher.py` | `graph` archetype `pure-logic` explicitly forbids OS/File I/O | DEFERRED (Pending Feature 3.48 Sidecar Databases which will abstract this into network-bound architecture) |
| `File I/O` inside `pure-logic` | `src/specweaver/assurance/graph/topology.py` (`TopologyGraph.from_project` globs `context.yaml`; `_auto_infer_missing` walks the tree) | `assurance/graph` archetype `pure-logic` forbids OS/File I/O | DEFERRED (`TECH-081` non-goal, 2026-10-27: recorded, not moved; same class as the `hasher.py` row) |
| `File I/O` inside `pure-logic` | `src/specweaver/assurance/validation/project_root.py` (`find_tests`, read by C02, C03 and the C03 hydrator) | `validation` archetype `pure-logic` forbids OS/File I/O | DEFERRED (`TECH-078` decision 2, 2026-10-24: one test-file search beside `walk_up`, where C02 already searched; moving it to the hydrator would lose C02 in `sw check`, which runs without hydration) |
| Inline Imports (Monolith Purge) | `core/flow/handlers/*`, `interfaces/cli/*` | Anti-Pattern: Hiding dependencies via inline imports to bypass `tach` or circular imports | DEFERRED (Pending dependency injection refactoring to pass domain stores dynamically) |
| `workspace/ast/adapters` consumed by `graph/core/builder` | `src/specweaver/graph/core/builder/orchestrator.py` (`_parseable_suffixes` → `parseable_suffixes`; `GraphOrchestrator.build_target` → `extract_ast_dict`) | `graph/core/builder` archetype `context.yaml` `allowed_imports` did not list `specweaver.workspace.ast.adapters`, and both imports were hidden inline — the recorded "hiding dependencies via inline imports" anti-pattern | **RESOLVED** (TECH-068 `AD-3`, user-approved architectural switch 2026-08-21, executed 2026-08-22). The dependency direction was always correct — `builder` is Application, `adapters` is Domain — and the import already existed; only the declaration was missing. Both imports are now at module level and the crossing is declared. **`tach check` could never catch this**: `tach.toml` already permits it and the rule lives only in `context.yaml`, which nothing read. The guardrail shipped with the fix is `tests/unit/graph/core/builder/test_declared_imports.py`, which asserts every module-level `specweaver.*` import in the package is covered by a declared prefix |
| `assurance/graph` consumed by `graph/core/builder` | `src/specweaver/graph/core/builder/orchestrator.py` (`load_topology`, lazy) | `graph` must not use `assurance/graph`, which uses `graph` (a loop) | OWED — `TECH-081` FR-17; `tach.toml` marks the edge `deprecated` |
| Root boundary manifest is a stub | `context.yaml` (repo root) | Declares `purpose: TODO` and `owner: TODO`, so the system-level manifest states no responsibility and names no owner — `context_yaml_spec.md` requires both, and every module manifest below it inherits a parent that says nothing | DEFERRED (found by the `specweaver-pre-commit` Phase 1 sweep on 2026-08-23 while retiring `TECH-069`, and deliberately left out of it: writing the system's one-sentence responsibility is a `T-ARCH` decision for the user, not something to slip into a retirement commit. Recorded rather than filled in, so nobody mistakes a guessed purpose for an agreed one) |

## Owed by TECH-081

Every edge `tach.toml` marks `deprecated` (`tach check` reports each import as `‼️`, never fails).
Each row names the `TECH-081` FR that removes it; `tests/unit/test_tach_sees_every_module.py` keeps
this table and `tach.toml` equal. A row goes when its edge goes; none may be added.

| Edge | What | Removed by |
|---|---|---|
| `specweaver.graph` → `specweaver.assurance.graph` | `orchestrator.py` loads the topology for a service name | FR-17 |
| `specweaver.graph.interfaces` → `specweaver.interfaces.cli` | the domain CLI imports the shell's `_core` helpers | FR-15 |
| `specweaver.assurance.standards.interfaces` → `specweaver.interfaces.cli` | the domain CLI imports the shell's `_core` helpers | FR-15 |
| `specweaver.assurance.validation.interfaces` → `specweaver.interfaces.cli` | the domain CLI imports the shell's `_core` helpers | FR-15 |
| `specweaver.core.config.interfaces` → `specweaver.interfaces.cli` | the domain CLI imports the shell's `_core` helpers | FR-15 |
| `specweaver.core.flow.interfaces` → `specweaver.interfaces.cli` | the domain CLI imports the shell's `_core` helpers | FR-15 |
| `specweaver.infrastructure.llm.interfaces` → `specweaver.interfaces.cli` | the domain CLI imports the shell's `_core` helpers | FR-15 |
| `specweaver.workflows.drafting.interfaces` → `specweaver.interfaces.cli` | the domain CLI imports the shell's `_core` helpers | FR-15 |
| `specweaver.workflows.implementation.interfaces` → `specweaver.interfaces.cli` | the domain CLI imports the shell's `_core` helpers | FR-15 |
| `specweaver.workflows.review.interfaces` → `specweaver.interfaces.cli` | the domain CLI imports the shell's `_core` helpers | FR-15 |
| `specweaver.workspace.project.interfaces` → `specweaver.interfaces.cli` | the domain CLI imports the shell's `_core` helpers | FR-15 |

## Resolved earlier

**Feature 3.32 SF-4 (Pipeline Execution Optimization)**

- **Sandbox Cache Caching (NFR-2)**: `flow/engine` now goes through `FileSystemAtom`, so path
  traversal boundaries are enforced. It replaced a local `os.symlink`, which broke the FileSystem
  boundary.
- **Cache-Flush Dilemma**: `flow/engine` must not consume `assurance/graph/hasher.py` to flush
  metrics after a pipeline. The flush lives in the `cli/pipelines.py` orchestrator, which may
  legally consume both layer roots.

**Feature 3.14 (Artifact Tagging Engine)**

- `llm/` forbids all imports from `sandbox/`, but the SF-02 plan had `prompt_builder.py` import
  `wrap_artifact_tag` from `specweaver.sandbox.lineage`. Fixed by moving `lineage.py` into the `llm`
  module (`specweaver/llm/lineage.py`) and exposing its utilities via `llm/context.yaml`.

**Feature 3.11a**

- Deleted `sandbox/research/` entirely
- Moved dispatcher to `sandbox/dispatcher.py` (sandbox root level)
- Consolidated `WorkspaceBoundary` into `sandbox/security.py`
- Tool definitions moved into each tool's own `definitions.py`
- `review/` and `planning/` use `sandbox/dispatcher` via `TYPE_CHECKING` only
- `flow/` consumes `sandbox/dispatcher` and `sandbox/security` at runtime (declared in `context.yaml`)
- `qa_runner/interfaces.py` tools→atoms import fixed to lazy factory import
