# Implementation Plan: ToolDispatcher Integration [SF-3]
- **Feature ID**: TECH-01b
- **Sub-Feature**: SF-3 — ToolDispatcher Integration
- **Design Document**: [TECH-01b_design.md](file:///c:/development/pitbula/specweaver/docs/roadmap/features/topic_07_technical_debt/TECH-01b/TECH-01b_design.md)
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-01b/TECH-01b_sf3_implementation_plan.md
- **Status**: COMPLETED

---

## 1. Research Notes

### 1.1 Current `create_standard_set` Anatomy

The existing `ToolDispatcher.create_standard_set` (dispatcher.py:99–239) is a 140-line `@classmethod` marked `# noqa: C901` (too complex). It contains:

- **4 conditional blocks** (fs, ast, web, mcp) with inline `from ... import` statements.
- **Duplicated grant-building logic** between fs and ast blocks (both iterate `boundary.roots` / `boundary.api_paths`).
- **Business logic embedded** in the factory: analyzer exclusion extraction, archetype resolution, evaluator schema loading, plugin resolution, hidden intent extraction.
- **No `qa` handling** — `QARunnerTool` is never instantiated by the dispatcher, only used directly by flow handlers and validation rules.
- **No `protocol` handling** — `ProtocolTool` is only accessible via the `ToolRegistry`, not via `create_standard_set`.
- **No `git` handling** — git interfaces are only accessible via the `ToolRegistry`, not via `create_standard_set`.

### 1.2 Call Sites

There are exactly **2 call sites** for `create_standard_set`:

1. **`core/flow/handlers/review.py:91`** — `_build_tool_dispatcher(context, role)` in the review handler. Passes: `boundary`, `role`, `allowed_tools=["fs", "ast", "web"?]`, `analyzer_factory`, `topology`.
2. **`core/flow/handlers/generation.py:15`** — imports `_build_tool_dispatcher` from `review.py` and reuses it for `PlanSpecHandler`.

Both go through the same `_build_tool_dispatcher` helper which:
- Creates a `WorkspaceBoundary.from_run_context(context)`
- Sets `allowed_tools = ["fs", "ast"]` (+ `"web"` if `SEARCH_API_KEY` is set)
- Passes `analyzer_factory` and `topology` from `RunContext`

### 1.3 `ToolRegistry` vs `ToolDispatcher` Role Division

| Responsibility | Current Owner | SF-3 Target |
|---|---|---|
| **Tool factory storage** | `ToolRegistry` ✅ | `ToolRegistry` (unchanged) |
| **Lazy domain import** | `ToolRegistry` closures ✅ | `ToolRegistry` closures (unchanged) |
| **Grant building** (RBAC filesystem/ast) | `ToolDispatcher.create_standard_set` | `ToolDispatcher.create_standard_set` (retained — this is role-specific business logic, not factory logic) |
| **Analyzer exclusion extraction** | `ToolDispatcher.create_standard_set` | `ToolDispatcher.create_standard_set` (retained — boundary-level concern) |
| **Archetype/plugin resolution** | `ToolDispatcher.create_standard_set` | `ToolDispatcher.create_standard_set` (retained — orchestrator-level concern) |
| **Intent registry building** | `ToolDispatcher.__init__` | `ToolDispatcher.__init__` (unchanged) |
| **Intent dispatch** | `ToolDispatcher.execute` | `ToolDispatcher.execute` (unchanged) |

> [!IMPORTANT]
> **Key Insight:** The design doc says "Remove `create_standard_set` hardcoded factory logic." However, the grant-building, archetype-resolution, and analyzer-exclusion logic is **not** factory logic — it is orchestrator-level business logic that must remain in the dispatcher (AD-7: registry stays dumb). What SF-3 removes is the **hardcoded import + instantiation** of each tool class. The dispatcher will call `registry.create_tools(...)` instead of inline `from ... import; tool = Tool(...)`.

### 1.4 Missing Registry Entries

| Tool Key | In `get_standard_registry()`? | In `create_standard_set`? | Notes |
|---|---|---|---|
| `"fs"` / `"filesystem"` | ✅ | ✅ | |
| `"ast"` / `"codestructure"` | ✅ | ✅ | |
| `"web"` | ✅ | ✅ | |
| `"mcp"` | ✅ | ✅ (architect only) | |
| `"git"` | ✅ | ❌ (never in dispatcher) | |
| `"protocol"` | ✅ | ❌ (never in dispatcher) | |
| `"qa"` / `"qa_runner"` | ❌ | ❌ | `QARunnerTool` exists but is not in either. Integration test requests `"qa"` but it's silently skipped. AD-9 only mentions `ProtocolTool`. |

### 1.5 Tach Boundary Analysis

- `core.flow` module's `context.yaml` already lists `specweaver/sandbox/dispatcher` in its `consumes` list → importing `ToolDispatcher` from flow handlers is legal.
- `core.flow` also consumes `specweaver/sandbox/security` → importing `WorkspaceBoundary`, `FolderGrant`, `AccessMode` from flow handlers is legal.
- `core.flow` **forbids** `specweaver/sandbox/*/interfaces` → flow handlers MUST NOT import tool facades/interfaces directly. They must go through `ToolDispatcher` or `ToolRegistry`.
- `sandbox` module in tach.toml `depends_on`: `workspace.ast.parsers`, `assurance.validation`, `core.config`, `infrastructure.llm`.
- `sandbox` expose list includes: `dispatcher`, `security`, `base`, `registry` — all needed by SF-3.

### 1.6 `QARunnerTool` Registration Decision (AD-9 Extension)

AD-9 says "Register `ProtocolTool` in standard registry" — already done in SF-1. The design doc does **not** mandate registering `QARunnerTool`. However:

- `QARunnerTool` requires a `QARunnerAtom(cwd=...)` and a role.
- It is currently only used by flow engine handlers (`ValidateTestsHandler`) which instantiate it directly via `QARunnerAtom(cwd=context.project_path)`.
- The integration test passing `"qa"` in `allowed_tools` works today because it's silently skipped.
- Registering it would require the dispatcher to instantiate `QARunnerAtom`, which adds complexity but no clear consumer benefit.

**Decision: Do NOT register `QARunnerTool` in SF-3.** It remains a flow-engine-internal tool. The `"qa"` key in integration tests should be documented as a no-op (silently skipped per existing `ToolRegistry` behavior).

### 1.7 Git Role Fallback (AD-10)

The `create_git_interface` factory in `git/interfaces/facades.py` already handles role fallback:
- `_ROLE_INTERFACE_MAP` maps `"scenario_agent"` → `ReviewerGitInterface` and `"arbiter_agent"` → `ReviewerGitInterface`.
- This means AD-10 is already implemented in the facade factory. No additional work needed in the dispatcher.

### 1.8 Existing Test Coverage

- **Unit tests** (`test_dispatcher.py`): 52 assertions across 16 test cases covering tool definitions, execute dispatch, protocol compliance, path grant matching, scenario agent isolation, AST initialization, analyzer factory DI, and MCP integration.
- **Unit tests** (`test_dispatcher_arbiter.py`): Arbiter agent grant logic and read-only boundary handling.
- **Unit tests** (`test_dispatcher_schema_hiding.py`): Hidden intent schema filtering and plugin-driven tool gate suppression.
- **Unit tests** (`test_registry.py`): 26 assertions across 14 test cases covering BaseTool ABC, ToolRegistry operations, lazy resolution, conformance, facade conformance.
- **Integration tests** (`test_dispatcher_sf2_integration.py`): 3 tests covering full tool set compliance, NO_ROLE sentinel, and topology pass-through.

---

## 2. Proposed Changes

### Component: Sandbox — Dispatcher

#### [MODIFY] [dispatcher.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/dispatcher.py)

**Goal:** Refactor `create_standard_set` to delegate tool instantiation to `ToolRegistry` while retaining orchestrator-level business logic (grant building, archetype resolution, analyzer exclusion extraction).

**Changes:**

1. Import `get_standard_registry` from `specweaver.sandbox.registry` (lazy, inside `create_standard_set`).
2. Replace the 4 inline import + instantiation blocks with a single `registry.create_tools(allowed_tools, **kwargs)` call.
3. Retain the grant-building logic (lines 120–161) and archetype/plugin resolution logic (lines 173–221) but restructure them to build a `kwargs` dict that gets passed to the registry.
4. Remove the inline `from ... import` statements for individual tool modules.
5. Reduce cyclomatic complexity sufficiently to remove the `# noqa: C901` marker.

**New `create_standard_set` structure:**

```python
@classmethod
def create_standard_set(
    cls,
    boundary: Any,
    role: str,
    allowed_tools: list[str],
    analyzer_factory: Any | None = None,
    topology: Any | None = None,
    parsers: Any | None = None,
) -> ToolDispatcher:
    from specweaver.sandbox.registry import get_standard_registry

    # 1. Build shared context that registry factories need
    kwargs = cls._build_registry_kwargs(
        boundary=boundary,
        role=role,
        allowed_tools=allowed_tools,
        analyzer_factory=analyzer_factory,
        topology=topology,
        parsers=parsers,
    )

    # 2. Delegate to ToolRegistry
    registry = get_standard_registry()
    tools = registry.create_tools(allowed_tools, **kwargs)

    return cls(tools)
```

6. Extract a new `@staticmethod _build_registry_kwargs(...)` method that:
   - Computes `grants` based on role + boundary (existing logic from lines 120–161)
   - Computes `exclude_dirs` / `exclude_patterns` from analyzer_factory (existing logic from lines 126–131)
   - Computes `cwd_path` from boundary roots (existing logic from line 163)
   - Resolves archetype, plugins, evaluator schemas, and builds `CodeStructureAtom` (existing logic from lines 173–221)
   - Computes `hidden_intents` from evaluator plugins (existing logic from lines 215–217)
   - Returns a flat `dict` with all computed kwargs

> [!WARNING]
> **`_build_registry_kwargs` is NOT a pure function.** It performs significant I/O and computation:
> file-system reads (loading evaluator schemas), archetype resolution (reading `context.yaml`),
> and `CodeStructureAtom` instantiation (creating `EngineFileExecutor`). Expect 100-200ms+ execution
> time on first call. This is acceptable — the same work was previously done inline in `create_standard_set`.

> [!WARNING]
> The `CodeStructureAtom` instantiation logic currently lives in `create_standard_set`. After SF-3, it moves into `_build_registry_kwargs`. This is still within `dispatcher.py` (same module), so no boundary violation occurs. The registry closure for `"ast"` receives the pre-built `atom` as a kwarg — **`atom` is a live object instance, not a serializable primitive.** The registry closure cherry-picks it via `kwargs["atom"]` and passes it directly to the `CodeStructureTool` constructor. It does NOT build atoms itself (AD-7 compliance).

**Signature preservation:** The public API of `create_standard_set` is unchanged. All existing call sites in `review.py` and `generation.py` continue to work without modification.

> [!IMPORTANT]
> **Tach compliance:** All sandbox domain imports inside `_build_registry_kwargs` (e.g. `from specweaver.sandbox.security import ...`, `from specweaver.sandbox.code_structure.core.atom import ...`) MUST remain **lazy** (inside the method body, not at module scope). Flow handlers import `ToolDispatcher` from `specweaver.sandbox.dispatcher`; if `dispatcher.py` had module-scope imports from `specweaver.sandbox.*.interfaces`, those would transitively violate `core.flow`'s `forbids: specweaver/sandbox/*/interfaces` boundary.

---

### Component: Sandbox — Registry

#### No changes to [registry.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/registry.py)

Per §1.6: `QARunnerTool` is NOT registered. It remains a flow-engine-internal tool. The `ToolRegistry` already handles unknown keys gracefully (logs warning, skips). No changes to `registry.py` are needed.

---

### Component: Flow Handlers

#### No changes required

Both call sites (`_build_tool_dispatcher` in `review.py` and its reuse in `generation.py`) already pass exactly the parameters that `create_standard_set` accepts. The refactored `create_standard_set` preserves the same signature, so no call-site changes are needed.

---

## 3. Verification Plan

### Automated Tests

**File: `tests/unit/sandbox/test_dispatcher.py`**

All 16 existing test cases must remain GREEN. No new tests needed here — the refactoring is internal to `create_standard_set` and the public API is unchanged.

Key tests that verify SF-3 correctness:
- `test_without_web` / `test_with_web` — verify tool filtering still works via registry delegation.
- `test_grep`, `test_find_files`, `test_read_file`, `test_list_directory` — verify execute dispatch still works.
- `test_unknown_tool`, `test_web_search_disabled`, `test_read_url_disabled` — verify unknown/disabled tools still error correctly.
- `test_scenario_agent_grants` — verify role-specific grant building still works.
- `test_dispatcher_loads_plugins` — verify archetype/plugin resolution still works.
- `test_dispatcher_fallback_graceful_on_exception` — verify archetype resolver crash handling.
- `test_dispatcher_fallback_safety_null_factory` — verify null analyzer_factory handling.
- `test_dispatcher_extracts_factory_excludes` — verify analyzer exclusion extraction.
- `test_mcp_granted_to_architect` / `test_mcp_ignored_for_reviewer` — verify MCP role gating.

**File: `tests/unit/sandbox/test_registry.py`**

All 14 existing test cases must remain GREEN. No changes needed.

**File: `tests/integration/sandbox/test_dispatcher_sf2_integration.py`**

All 3 existing integration tests must remain GREEN.

**New test file: `tests/integration/sandbox/test_dispatcher_sf3_integration.py`**

New integration tests to verify the registry delegation:

1. `test_create_standard_set_delegates_to_registry` — Monkey-patch `get_standard_registry` to return a mock `ToolRegistry`, verify `create_tools` is called with the correct `allowed_tools` and kwargs containing `role`, `cwd`, `grants`, etc.
2. `test_create_standard_set_preserves_grant_logic` — Create a dispatcher with `role="scenario_agent"` and verify the resulting tool grants are identical to the pre-SF-3 behavior (scenarios + contracts dirs, not full root).
3. `test_create_standard_set_preserves_archetype_resolution` — Create a project with `context.yaml` specifying an archetype, verify the `CodeStructureAtom` receives the correct archetype.

### Manual Verification

1. Run full dispatcher test suite (expect all green):
   `uv run pytest tests/unit/sandbox/test_dispatcher.py tests/unit/sandbox/test_dispatcher_arbiter.py tests/unit/sandbox/test_dispatcher_schema_hiding.py tests/unit/sandbox/test_registry.py tests/integration/sandbox/test_dispatcher_sf2_integration.py -v`

2. Run tach check (must not increase violation count from baseline of 95):
   `uv run tach check 2>&1 | Select-String "FAIL" | Measure-Object`

3. Verify `# noqa: C901` removal via linting (no function should exceed complexity 10):
   `uv run flake8 src/specweaver/sandbox/dispatcher.py --select=C901 --max-complexity=10`

4. Run full test suite to verify zero regression:
   `uv run pytest tests/ -x --timeout=120`

---

## 4. Commit Boundaries

### Single Commit: SF-3 ToolDispatcher Integration

**Production code:**
- `dispatcher.py` — refactor `create_standard_set` to delegate to `ToolRegistry`

**Tests:**
- `tests/integration/sandbox/test_dispatcher_sf3_integration.py` [NEW] — 3 integration tests for registry delegation

---

## 5. ROI Analysis

### Pros
1. **Reduced complexity**: `create_standard_set` drops from ~140 lines / C901 to ~30 lines + a clean helper method.
2. **Single composition root**: Tool instantiation is centralized in `ToolRegistry` (AD-3). Adding a new tool domain requires only adding a factory closure in `registry.py` — no dispatcher changes.
3. **Testability**: Registry factories can be independently tested. The dispatcher can be tested with mock registries.
4. **Future extensibility**: SF-4 (Validation Isolation) benefits because validation handlers can use `ToolRegistry` directly if needed, without coupling to `ToolDispatcher`.
5. **DRY**: Eliminates duplicated import patterns across `create_standard_set` and `get_standard_registry`.

### Cons
1. **Indirection cost**: One extra hop (dispatcher → registry → factory closure) vs. direct inline construction.
2. **kwargs coupling**: The dispatcher must build a superset kwargs dict that all factories can cherry-pick from. If a new factory needs a new kwarg, the dispatcher must provide it.
3. **Migration risk**: Any subtle behavioral difference in the refactored grant/archetype logic could break existing functionality silently.

### Refactoring Opportunities for Existing Features

1. **`_build_tool_dispatcher` in review.py**: Currently duplicates the `WorkspaceBoundary.from_run_context` + `allowed_tools` + `ToolDispatcher.create_standard_set` pattern. After SF-3, this helper becomes even thinner since the dispatcher handles everything.
2. **Validation rules C03/C04/C05**: SF-4 will remove their direct `QARunnerAtom` imports. SF-3 establishes the pattern that tools are only accessed through the registry/dispatcher composition root.
3. **Future tool additions**: Any new tool domain (e.g., Docker, Terraform) would follow the same pattern: add a factory closure in `registry.py`, done.

---

## 6. Open Questions for HITL Review

*(To be populated during Phase 2/3 audit)*
