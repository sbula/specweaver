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
| Unenforceable boundary: `specweaver/commons` | `src/specweaver/commons/` (consumed at module level by `core/flow/engine/{display,runner,store}.py`, `core/flow/handlers/{arbiter,decompose,drift}.py`, and others) | Declares `archetype: raw-data`, `consumes: []`, `forbids: specweaver/*` in its `context.yaml`, but is **not registered in `tach.toml`** — so `tach check` can neither verify that `commons` stays dependency-free nor police who consumes it | DEFERRED (same class as the `workspace/store.py` NFR-2 row above. The dependency direction is *correct* — `commons` is an L0 foundation leaf every layer may legally depend on — but the rule is currently unenforced. Fix = register `specweaver.commons` as a tach module with an empty `depends_on`; deferred because that sweep may surface unrelated violations across the repo and belongs in a dedicated boundary-hygiene ticket, not in INT-US-21) |
| `drafting` consumed by `core/flow` | `src/specweaver/core/flow/handlers/draft.py` (`DraftSpecHandler._execute_drafting` → `Drafter`; `DraftFeatureHandler._execute_drafting` → `FeatureDrafter`) | `core/flow` archetype `context.yaml` explicitly `forbids: specweaver/drafting` ("Rules and adapters must remain isolated from interactive drafts") | DEFERRED (INT-US-21 AD-3, user-approved architectural switch 2026-07-24. **`tach check` cannot catch this** — `tach.toml` already permits `specweaver.core.flow → specweaver.workflows.drafting`, so the rule lives only in `context.yaml`. Pre-existing via `DraftSpecHandler`; `DraftFeatureHandler` extends the same seam rather than opening a new violation class. Destination: the dependency-injection refactor tracked by the Inline Imports (Monolith Purge) row above) |
| `workspace/ast/adapters` consumed by `graph/core/builder` | `src/specweaver/graph/core/builder/orchestrator.py` (`_parseable_suffixes` → `parseable_suffixes`; `GraphOrchestrator.build_target` → `extract_ast_dict`) | `graph/core/builder` archetype `context.yaml` `allowed_imports` did not list `specweaver.workspace.ast.adapters`, and both imports were hidden inline — the recorded "hiding dependencies via inline imports" anti-pattern | **RESOLVED** (TECH-068 `AD-3`, user-approved architectural switch 2026-08-21, executed 2026-08-22). The dependency direction was always correct — `builder` is Application, `adapters` is Domain — and the import already existed; only the declaration was missing. Both imports are now at module level and the crossing is declared. **`tach check` could never catch this**: `tach.toml` already permits it and the rule lives only in `context.yaml`, which nothing read. The guardrail shipped with the fix is `tests/unit/graph/core/builder/test_declared_imports.py`, which asserts every module-level `specweaver.*` import in the package is covered by a declared prefix |
| `assurance/graph` consumed by `graph/core/builder` | `src/specweaver/graph/core/builder/orchestrator.py` (`GraphOrchestrator.build_target` → `load_topology`, inline) | `graph/core/builder` archetype `context.yaml` `allowed_imports` does not list `specweaver.assurance` | DEFERRED (found while executing TECH-068 `AD-3` on 2026-08-22 and deliberately left out of it: `AD-3` names the adapters crossing only, and declaring `specweaver.assurance` here is a separate architectural claim nobody has made. Recorded rather than lifted, so the guardrail test above stays module-level and cannot silently legitimise it. Same class as the `Inline Imports (Monolith Purge)` row) |
| Root boundary manifest is a stub | `context.yaml` (repo root) | Declares `purpose: TODO` and `owner: TODO`, so the system-level manifest states no responsibility and names no owner — `context_yaml_spec.md` requires both, and every module manifest below it inherits a parent that says nothing | DEFERRED (found by the `specweaver-pre-commit` Phase 1 sweep on 2026-08-23 while retiring `TECH-069`, and deliberately left out of it: writing the system's one-sentence responsibility is a `T-ARCH` decision for the user, not something to slip into a retirement commit. Recorded rather than filled in, so nobody mistakes a guessed purpose for an agreed one) |

> **Resolved in Feature 3.32 SF-4 (Pipeline Execution Optimization):**
> - **Sandbox Cache Caching (NFR-2)**: Initially, `flow/engine` utilized `os.symlink` locally. This
>   was struck down as an architectural violation of the FileSystem boundaries. It was refactored
>   strictly to trigger `FileSystemAtom` natively ensuring path traversal boundaries are enforced.
> - **Cache-Flush Dilemma**: We intentionally prevented `flow/engine` from consuming
>   `assurance/graph/hasher.py` to trigger the actual metric flush post-pipeline. Instead, we
>   shifted the operation purely to the `cli/pipelines.py` orchestrator which legally consumes both
>   layer roots.

> **Resolved in Feature 3.14 (Artifact Tagging Engine)**
> The implementation plan for SF-02 explicitly instructed `prompt_builder.py` to import
> `wrap_artifact_tag` from `specweaver.sandbox.lineage`. However, `llm/` strictly forbids all
> imports from `sandbox/`. I resolved this by immediately relocating `lineage.py` into the `llm`
> module natively (`specweaver/llm/lineage.py`) and exposing its utilities via `llm/context.yaml`.

> **Resolved in Feature 3.11a:**
> - Deleted `sandbox/research/` entirely
> - Moved dispatcher to `sandbox/dispatcher.py` (sandbox root level)
> - Consolidated `WorkspaceBoundary` into `sandbox/security.py`
> - Tool definitions moved into each tool's own `definitions.py`
> - `review/` and `planning/` use `sandbox/dispatcher` via `TYPE_CHECKING` only
> - `flow/` consumes `sandbox/dispatcher` and `sandbox/security` at runtime (declared in `context.yaml`)
> - `qa_runner/interfaces.py` tools→atoms import fixed to lazy factory import
