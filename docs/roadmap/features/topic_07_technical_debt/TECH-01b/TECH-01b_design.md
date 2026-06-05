# Design: BaseTool Metaclass Registry Refactoring

- **Feature ID**: TECH-01b
- **Phase**: 1
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-01b/TECH-01b_design.md

## Feature Overview

Feature TECH-01b adds an explicit, decoupled ToolRegistry to the specweaver.sandbox component.
It solves the tight coupling of dynamic imports and boundary bypasses in ToolDispatcher by removing implicit global metaclass auto-registration and replacing it with explicit domain-level tool list exports.
It interacts with all sandbox domain tools (git, filesystem, qa_runner, mcp, protocol, web, code_structure) and does NOT touch actual LLM model adapters or core SQLite CQRS database schemas.
Key constraints: zero regression (all tests must pass) and targeted enforcement of context.yaml boundaries in the validation rules layer (removing direct sandbox imports in c03, c04, c05).

## Research Findings

### Codebase Patterns
- Currently, `ToolDispatcher` contains hardcoded conditional imports and execution logic to assemble the set of tools for a given role and boundary.
- The original design of `TECH-01` deferred implementing `BaseTool` metaclass auto-registration because global import-time auto-registration pollutes the memory space and bypasses isolation limits.
- Validation layer rules `c03_tests_pass.py`, `c04_coverage.py`, and `c05_import_direction.py` import `QARunnerAtom` and `AtomStatus` directly, causing `context.yaml` violations. These are resolved by pre-running the atoms in the flow layer and injecting results into `Rule.context`.
- The `sandbox` module depends on `specweaver.assurance.validation` via `rule_atom.py` (adapter pattern: wraps a `Rule` into an `Atom`). This is intentional and non-circular. The reverse dependency (`validation → sandbox`) is what is forbidden by `context.yaml` and is what TECH-01b removes.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Tach | 0.1.0+ | `check` | `pyproject.toml` |

### Blueprint References
- [special_patterns_and_adaptations.md](file:///c:/development/pitbula/specweaver/docs/dev_guides/special_patterns_and_adaptations.md): Outlines `context.yaml` boundaries and rule context hydration pattern.
- [layer_isolation_and_di.md](file:///c:/development/pitbula/specweaver/docs/dev_guides/layer_isolation_and_di.md): Outlines standard dependency injection across orchestrator layers.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------| 
| FR-1 | BaseTool Base Class | System | Define abstract BaseTool | Exposes `role` and `definitions` as the minimal contract for all tool facades. |
| FR-2 | ToolRegistry core | System | Implement ToolRegistry | Allows registering tool factory callables and instantiating them dynamically. |
| FR-3 | Decouple Dispatcher | ToolDispatcher | Delegate tool creation to ToolRegistry | Replaces hardcoded tool builder blocks with registry queries. |
| FR-4 | Domain Explicit Registration | Sandbox Domains | Conform to BaseTool and export factories | Each domain facade inherits `BaseTool` and registers its factory explicitly. |
| FR-5 | Inject rule dependencies | core.flow handlers | Pre-run QA atoms; inject results into Rule.context | Eliminates direct sandbox imports in pure-logic validation rules (c03, c04, c05). |
| FR-6 | CLI/API validation routing | interfaces.cli + interfaces.api | Route validations through flow layer | Prevents L4 Interface modules from importing sandbox components directly, maintaining strict boundary rules. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Zero Regression | 100% of unit, integration, and E2E tests must pass. |
| NFR-2 | No Side-Effects | Importing a tool module must not populate global registries or run registration side-effects. |
| NFR-3 | Strict Isolation | Remove direct `sandbox` imports from `validation/rules/code/c03`, `c04`, `c05`. |
| NFR-4 | Boundary Enforcement | TECH-01b must not introduce new `tach check` violations. The c03/c04/c05 violations must be resolved. Pre-existing baseline violations (95 at time of writing, unrelated to this feature) remain out of scope. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Tach | 0.1.0 | `check` | Yes | Handles boundary enforcement checks. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Put `BaseTool` in `sandbox/base.py` | Matches the existing location of `Atom` and keeps base abstractions consolidated. | No |
| AD-2 | `BaseTool` contract = `role` + `definitions()` only; **no** `allowed_intents` | The facade RBAC pattern enforces intent restrictions by physically removing methods. An `allowed_intents` property would duplicate this structural guarantee redundantly. No caller (dispatcher, flow engine) reads `allowed_intents`. Removing it makes every existing facade conformant by adding only one `role` delegation property. KISS wins. | Yes |
| AD-3 | `get_standard_registry()` is the composition root for `sandbox` | DDD purists would have domains self-register. However, treating `get_standard_registry()` as the composition root is pragmatic, testable, and consistent with the existing `ToolDispatcher.create_standard_set` pattern it replaces. Internal `sandbox` sub-module dependencies are legal under the current tach configuration. | No |
| AD-4 | Flow layer context hydration for validation rules | The execution of `QARunnerAtom` (for c03/c04/c05) MUST happen in `core.flow` (the only layer allowed to orchestrate both sandbox and validation). `core.flow` pre-runs the atom, then injects the result into the `context` arg of `execute_validation_pipeline`. This is the only way to truly isolate the `validation` layer from `sandbox`. | Yes |
| AD-5 | Route validation through a flow orchestrator entry point | L4 Interface modules (CLI and API) are forbidden from importing sandbox components directly by `cli/context.yaml` and `api/context.yaml`. To prevent boundary violations, the CLI and API will delegate validation checks to a new `execute_validation_flow` entry point in `core.flow`, which performs hydration and triggers the pipeline. | Yes |
| AD-6 | Refactor `MCPExplorerTool` to accept `topology` directly | The `DummyContext` wrapper class in `get_standard_registry()` (and in the original `ToolDispatcher`) is a DRY violation. `MCPExplorerTool.__init__` will be changed to accept `topology: Any = None` directly, removing the need for any wrapper. | No |
| AD-7 | Registry Separation of Concerns | `ToolRegistry` must remain a simple factory store. Business logic (e.g., `arbiter_agent` fallbacks for FS, or analyzer setups) must be encapsulated in the domain facade factories (e.g. `create_filesystem_interface`) or the `ToolDispatcher`, not within `registry.py` closures. | Yes |
| AD-8 | Optimize QA executions | The validation orchestrator in `core.flow` must check if the code rules (C03, C04, C05) are active before calling `QARunnerAtom` to prevent slow subprocess calls for disabled rules. | No |
| AD-9 | Register `ProtocolTool` in standard registry | `ProtocolTool` is a sandbox domain tool and must be registered via dynamic lazy-factory inside `get_standard_registry()` to satisfy full interface coverage. | No |
| AD-10 | Provide Git interface fallback for read-only agent roles | Ensure `create_git` factory maps read-only agent roles (`scenario_agent`, `arbiter_agent`) to the `"reviewer"` Git interface to prevent setup crashes for diagnostic executions. | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Guide-1 | How to expose and register a new sandbox tool | ⬜ To be written during Pre-commit |
| Guide-2 | How to write a validation rule that receives injected context | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: BaseTool and ToolRegistry Core
- **Scope**: Define `BaseTool` abstract base class (`role` + `definitions()` only — no `allowed_intents`) and implement `ToolRegistry` in `specweaver.sandbox`. Add `isinstance(tool, BaseTool)` assertions to the SF-1 test file — these tests will be **RED** until SF-2 makes all domain facades conform. This is the TDD red-phase for SF-2.
- **FRs**: [FR-1, FR-2]
- **Inputs**: Registry registrations.
- **Outputs**: Instantiated tools list.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-01b/TECH-01b_sf1_implementation_plan.md

### SF-2: Sandbox Domain Alignment
- **Scope**: Make all domain tool facades inherit `BaseTool` by adding `(BaseTool)` and a delegating `role` property where missing. Affected classes: `FileSystemTool`, `ReviewerFileInterface`, `ImplementerFileInterface`, `DrafterFileInterface`, `GitTool`, `ImplementerGitInterface`, `ReviewerGitInterface`, `DebuggerGitInterface`, `DrafterGitInterface`, `ConflictResolverGitInterface`, `WebTool`, `CodeStructureTool`, `ArchitectMCPInterface`, `ProtocolTool`. Also refactor `MCPExplorerTool.__init__` to accept `topology: Any = None` directly, removing all `DummyContext` wrapper usages from both `registry.py` and `dispatcher.py` (AD-6). The `isinstance(tool, BaseTool)` assertions in `test_registry.py` must turn GREEN.
- **FRs**: [FR-4]
- **Inputs**: `BaseTool` ABC from SF-1.
- **Outputs**: All domain facades are `BaseTool`-conformant; `isinstance` tests pass.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-01b/TECH-01b_sf2_implementation_plan.md

### SF-3: ToolDispatcher Integration
- **Scope**: Refactor `ToolDispatcher` to build standard tool sets by delegating construction to `ToolRegistry`. Remove `create_standard_set` hardcoded factory logic. Wire `get_standard_registry()` into the flow engine entry points. Register `"protocol"` factory dynamically inside `get_standard_registry()` (AD-9) and handle Git role fallbacks (AD-10).
- **FRs**: [FR-3]
- **Inputs**: Configured `ToolRegistry` from SF-1 (functionally does not require SF-2, but follows SF-2 in recommended order so the dispatcher can add `BaseTool` type assertions).
- **Outputs**: Reusable configured `ToolDispatcher`.
- **Depends on**: SF-2 (recommended; functionally only requires SF-1)
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-01b/TECH-01b_sf3_implementation_plan.md

### SF-4: Validation Layer Isolation
- **Scope**: Remove direct `QARunnerAtom` and `AtomStatus` imports from `c03_tests_pass.py`, `c04_coverage.py`, and `c05_import_direction.py`. Rules must read execution results from `self.context` using agreed keys (see below). Refactor all three call sites to route through `specweaver.core.flow`'s new `execute_validation_flow` handler: (1) `ValidateCodeHandler._run_validation` in `core.flow.handlers.validation`, (2) the standalone CLI check command, (3) `interfaces.api.v1.validation`. Update rule check logic for C03 so that if test files exist but the context key is missing, it fails/warns instead of silently skipping. Remove the `forbids: specweaver/sandbox/*` violation from validation context files once no direct imports remain.

  **Context key contract** (rules read from `self.context`):
  - `"qa_tests_result"` → `AtomResult`-like dict from `QARunnerAtom.run({"intent": "run_tests", ...})`
  - `"qa_coverage_result"` → `AtomResult`-like dict from `QARunnerAtom.run({"intent": "run_tests", "coverage": True, ...})`
  - `"qa_architecture_result"` → `AtomResult`-like dict from `QARunnerAtom.run({"intent": "run_architecture", ...})`
  - If a key is absent → rule calls `self._skip(...)` or `self._fail(...)` (for C03/C04 if test files are present).
- **FRs**: [FR-5, FR-6]
- **Inputs**: Hydrated `Rule.context` injected by all three callers.
- **Outputs**: Isolated validation layer; zero direct sandbox imports in validation rules.
- **Depends on**: SF-3
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-01b/TECH-01b_sf4_implementation_plan.md

## Execution Order

1. SF-1 (BaseTool and ToolRegistry Core) — no deps, start immediately.
2. SF-2 (Sandbox Domain Alignment) — depends on SF-1; turns red conformance tests green.
3. SF-3 (ToolDispatcher Integration) — depends on SF-2.
4. SF-4 (Validation Layer Isolation) — depends on SF-3.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | BaseTool & Registry | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Sandbox Alignment | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-3 | Dispatcher Integration | SF-2 | ✅ | ✅ | ✅ | ✅ | ⬜ |
| SF-4 | Validation Isolation | SF-3 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

## Handoff

**Current status**: SF-3 implementation plan approved.
**Next step**: Run `/dev docs/roadmap/features/topic_07_technical_debt/TECH-01b/TECH-01b_sf3_implementation_plan.md` to begin implementation.
