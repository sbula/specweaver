# Known Boundary Violations

| Violation | Where | Rule Broken | Status |
|-----------|-------|-------------|--------|
| `sandbox/*` consumed by `llm` | `src/specweaver/llm/prompt_builder.py` | `llm` archetype `context.yaml` explicitly `forbids: specweaver/sandbox/*` | FIXED (CB-2 Gate Phase 1) |
| `sandbox/*` consumed by `validation` | `src/specweaver/validation/rules/code/` (C03, C04, C05) | `validation` archetype `context.yaml` explicitly `forbids: specweaver/sandbox/*` | DEFERRED (Pending review on whether `commons/qa_runner` executor usage is appropriate inside pure-logic rules via contextual bypasses, or if it should be extracted strictly natively into `flow/` orchestrated tasks) |
| `File I/O` inside `pure-logic` | `src/specweaver/assurance/graph/hasher.py` | `graph` archetype `pure-logic` explicitly forbids OS/File I/O | DEFERRED (Pending Feature 3.48 Sidecar Databases which will abstract this into network bound architecture natively) |
| `File I/O` inside `pure-logic` | `src/specweaver/workspace/ast/parsers/exclusions.py` | `workspace/ast/parsers` archetype `pure-logic` forbids OS/File I/O | DEFERRED (Pending Feature 3.32b SF-4 which abstracts physical OS traversals securely via dependency injection bounds) |
| Inline Imports (Monolith Purge) | `core/config/database.py`, `core/config/settings.py`, `core/flow/handlers/*`, `interfaces/cli/*` | Anti-Pattern: Hiding dependencies via inline imports to bypass `tach` or circular imports | DEFERRED (Pending dependency injection refactoring to pass domain stores dynamically) |
| Stability Direction Violation | `core/config/database.py`, `core/config/settings.py` | `config` (stable leaf) consumes `workspace` and `llm` (volatile domains) | DEFERRED (Pending dependency injection refactoring for DB initialization) |
| NFR-2 Boundary Evasion | `src/specweaver/workspace/store.py` | Missing `context.yaml` and not registered in `tach.toml`, causing `tach check` to ignore its boundary violations | DEFERRED (Pending proper module registration for workspace root) |


> **Resolved in Feature 3.32 SF-4 (Pipeline Execution Optimization):**
> - **Sandbox Cache Caching (NFR-2)**: Initially, `flow/engine` utilized `os.symlink` locally. This was struck down as an architectural violation of the FileSystem boundaries. It was refactored strictly to trigger `FileSystemAtom` natively ensuring path traversal boundaries are enforced.
> - **Cache-Flush Dilemma**: We intentionally prevented `flow/engine` from consuming `assurance/graph/hasher.py` to trigger the actual metric flush post-pipeline. Instead, we shifted the operation purely to the `cli/pipelines.py` orchestrator which legally consumes both layer roots.

> **Resolved in Feature 3.14 (Artifact Tagging Engine)**
> The implementation plan for SF-2 explicitly instructed `prompt_builder.py` to import `wrap_artifact_tag` from `specweaver.sandbox.lineage`. However, `llm/` strictly forbids all imports from `sandbox/`. I resolved this by immediately relocating `lineage.py` into the `llm` module natively (`specweaver/llm/lineage.py`) and exposing its utilities via `llm/context.yaml`.

> **Resolved in Feature 3.11a:**
> - Deleted `sandbox/research/` entirely
> - Moved dispatcher to `sandbox/dispatcher.py` (sandbox root level)
> - Consolidated `WorkspaceBoundary` into `sandbox/security.py`
> - Tool definitions moved into each tool's own `definitions.py`
> - `review/` and `planning/` use `sandbox/dispatcher` via `TYPE_CHECKING` only
> - `flow/` consumes `sandbox/dispatcher` and `sandbox/security` at runtime (declared in `context.yaml`)
> - `qa_runner/interfaces.py` tools→atoms import fixed to lazy factory import
