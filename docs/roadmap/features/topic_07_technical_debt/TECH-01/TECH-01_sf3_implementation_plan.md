# Implementation Plan: Domain-Driven Design Unification [SF-3: Consolidate Sandbox]

- **Feature ID**: TECH-01
- **Sub-Feature**: SF-3 — Consolidate Sandbox
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-01/TECH-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-01/TECH-01_sf3_implementation_plan.md
- **Status**: APPROVED

## Goal

Reorganize `core/loom/` from **Package-by-Layer** (`atoms/`, `tools/`, `commons/`) into **Package-by-Domain** under `src/specweaver/sandbox/`. Each domain adopts the SF-2 hexagonal architecture pattern (`core/` + `interfaces/` sub-packages) with machine-enforceable boundary sealing.

> [!CAUTION]
> **NFR-1 Zero Regression**: 546 import references across 152 files (54 src + 98 tests) must be rewritten. Zero test assertion changes allowed.

## Architectural Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| AD-1 | Full rename `core/loom/` → `sandbox/` | Matches design doc AD-2. Zero external consumers. |
| AD-2 | Hexagonal architecture per domain | SF-2 pattern: `core/` (sealed) + `interfaces/` (facade). Machine-enforceable via `context.yaml`. |
| AD-3 | NFR-6 (`BaseTool` metaclass) deferred | Out of scope — add to tech debt backlog as TECH-01b. |
| AD-4 | Rename `tools/{domain}/interfaces.py` → `facades.py` | Avoids `interfaces.interfaces` double-name collision. |
| AD-5 | Historical docs NOT updated | Completed plans for other features document decisions against the old layout. Only active reference docs are updated. |

## Design Requirements Compliance Matrix

| Requirement | Addressed By | Notes |
|-------------|-------------|-------|
| **FR-6** Group atoms/tools/commons into feature directories | Target Layout + hex structure | Each domain colocates all layers |
| **NFR-1** Zero Regression | Verification Plan (full test suite) | Zero assertion changes |
| **NFR-2** Boundary Enforcement (context.yaml + tach.toml) | Per-domain context.yaml + tach.toml rewrite | See exhaustive context.yaml rewrite section |
| **NFR-6** Meta-Class Registry (BaseTool) | AD-3: Deferred to TECH-01b | Out of FR-6 scope |
| **AD-2** Rename loom → sandbox/ | AD-1: Full rename | 546 references rewritten |

## Target Layout

```
src/specweaver/sandbox/
├── dispatcher.py                        ← from core/loom/dispatcher.py
├── security.py                          ← from core/loom/security.py
├── base.py                              ← from core/loom/atoms/base.py
├── rule_atom.py                         ← from core/loom/atoms/rule_atom.py
├── context.yaml
│
├── git/
│   ├── core/
│   │   ├── executor.py                  ← from commons/git/executor.py
│   │   ├── engine_executor.py           ← from commons/git/engine_executor.py
│   │   ├── atom.py                      ← from atoms/git/atom.py
│   │   ├── worktree_ops.py              ← from atoms/git/worktree_ops.py
│   │   └── context.yaml                 ← forbids: sandbox/git/interfaces
│   ├── interfaces/
│   │   ├── tool.py                      ← from tools/git/tool.py
│   │   ├── facades.py                   ← from tools/git/interfaces.py (RENAMED)
│   │   ├── definitions.py               ← from tools/git/definitions.py
│   │   └── context.yaml                 ← consumes: sandbox/git/core
│   └── context.yaml
│
├── filesystem/
│   ├── core/
│   │   ├── executor.py                  ← from commons/filesystem/executor.py
│   │   ├── search.py                    ← from commons/filesystem/search.py
│   │   ├── atom.py                      ← from atoms/filesystem/atom.py
│   │   └── context.yaml
│   ├── interfaces/
│   │   ├── tool.py                      ← from tools/filesystem/tool.py
│   │   ├── facades.py                   ← from tools/filesystem/interfaces.py (RENAMED)
│   │   ├── models.py                    ← from tools/filesystem/models.py
│   │   ├── definitions.py               ← from tools/filesystem/definitions.py
│   │   └── context.yaml
│   └── context.yaml
│
├── qa_runner/
│   ├── core/
│   │   ├── interface.py                 ← from commons/qa_runner/interface.py
│   │   ├── factory.py                   ← from commons/qa_runner/factory.py
│   │   ├── atom.py                      ← from atoms/qa_runner/atom.py
│   │   └── context.yaml
│   ├── interfaces/
│   │   ├── tool.py                      ← from tools/qa_runner/tool.py
│   │   ├── facades.py                   ← from tools/qa_runner/interfaces.py (RENAMED)
│   │   ├── definitions.py               ← from tools/qa_runner/definitions.py
│   │   └── context.yaml
│   └── context.yaml
│
├── mcp/
│   ├── core/
│   │   ├── executor.py                  ← from commons/mcp/executor.py
│   │   ├── atom.py                      ← from atoms/mcp/atom.py
│   │   └── context.yaml
│   ├── interfaces/
│   │   ├── tool.py                      ← from tools/mcp/tool.py
│   │   ├── facades.py                   ← from tools/mcp/interfaces.py (RENAMED)
│   │   ├── definitions.py               ← from tools/mcp/definitions.py
│   │   ├── models.py                    ← from tools/mcp/models.py
│   │   └── context.yaml
│   └── context.yaml
│
├── protocol/
│   ├── core/
│   │   ├── asyncapi_parser.py           ← from commons/protocol/
│   │   ├── grpc_parser.py
│   │   ├── openapi_parser.py
│   │   ├── factory.py
│   │   ├── protocol_interfaces.py       ← from commons/protocol/interfaces.py (RENAMED)
│   │   ├── models.py
│   │   ├── atom.py                      ← from atoms/protocol/atom.py
│   │   └── context.yaml
│   ├── interfaces/
│   │   ├── tool.py                      ← from tools/protocol/tool.py
│   │   └── context.yaml
│   └── context.yaml
│
├── web/                                 ← Tool-only domain — no core/
│   ├── interfaces/
│   │   ├── tool.py                      ← from tools/web/tool.py
│   │   ├── facades.py                   ← from tools/web/interfaces.py (RENAMED)
│   │   ├── definitions.py               ← from tools/web/definitions.py
│   │   └── context.yaml
│   └── context.yaml
│
├── language/                            ← Engine-only domain — no interfaces/
│   ├── core/
│   │   ├── _detect.py                   ← from commons/language/
│   │   ├── evaluator.py
│   │   ├── scenario_converter_factory.py
│   │   ├── stack_trace_filter_factory.py
│   │   ├── atom.py                      ← from atoms/language/atom.py
│   │   ├── java/                        ← from commons/language/java/
│   │   ├── kotlin/
│   │   ├── python/
│   │   ├── rust/
│   │   ├── typescript/
│   │   └── context.yaml
│   └── context.yaml
│
└── code_structure/
    ├── core/
    │   ├── atom.py                      ← from atoms/code_structure/atom.py
    │   └── context.yaml
    ├── interfaces/
    │   ├── tool.py                      ← from tools/code_structure/tool.py
    │   ├── definitions.py               ← from tools/code_structure/definitions.py
    │   └── context.yaml
    └── context.yaml
```

## Import Path Mapping Table

> [!CAUTION]
> **MANDATORY**: Use this table mechanically. Do NOT infer mappings. This table covers ALL import prefixes. `@patch()` string literals use the same mapping.

### Layer: `commons/` → `core/`

| Old Import Prefix | New Import Prefix |
|-------------------|-------------------|
| `specweaver.core.loom.commons.git.executor` | `specweaver.sandbox.git.core.executor` |
| `specweaver.core.loom.commons.git.engine_executor` | `specweaver.sandbox.git.core.engine_executor` |
| `specweaver.core.loom.commons.filesystem.executor` | `specweaver.sandbox.filesystem.core.executor` |
| `specweaver.core.loom.commons.filesystem.search` | `specweaver.sandbox.filesystem.core.search` |
| `specweaver.core.loom.commons.qa_runner.interface` | `specweaver.sandbox.qa_runner.core.interface` |
| `specweaver.core.loom.commons.qa_runner.factory` | `specweaver.sandbox.qa_runner.core.factory` |
| `specweaver.core.loom.commons.mcp.executor` | `specweaver.sandbox.mcp.core.executor` |
| `specweaver.core.loom.commons.protocol.interfaces` | `specweaver.sandbox.protocol.core.protocol_interfaces` |
| `specweaver.core.loom.commons.protocol.models` | `specweaver.sandbox.protocol.core.models` |
| `specweaver.core.loom.commons.protocol.factory` | `specweaver.sandbox.protocol.core.factory` |
| `specweaver.core.loom.commons.protocol.asyncapi_parser` | `specweaver.sandbox.protocol.core.asyncapi_parser` |
| `specweaver.core.loom.commons.protocol.grpc_parser` | `specweaver.sandbox.protocol.core.grpc_parser` |
| `specweaver.core.loom.commons.protocol.openapi_parser` | `specweaver.sandbox.protocol.core.openapi_parser` |
| `specweaver.core.loom.commons.language.*` | `specweaver.sandbox.language.core.*` |

### Layer: `atoms/` → `core/`

| Old Import Prefix | New Import Prefix |
|-------------------|-------------------|
| `specweaver.core.loom.atoms.git.atom` | `specweaver.sandbox.git.core.atom` |
| `specweaver.core.loom.atoms.git.worktree_ops` | `specweaver.sandbox.git.core.worktree_ops` |
| `specweaver.core.loom.atoms.filesystem.atom` | `specweaver.sandbox.filesystem.core.atom` |
| `specweaver.core.loom.atoms.qa_runner.atom` | `specweaver.sandbox.qa_runner.core.atom` |
| `specweaver.core.loom.atoms.mcp.atom` | `specweaver.sandbox.mcp.core.atom` |
| `specweaver.core.loom.atoms.protocol.atom` | `specweaver.sandbox.protocol.core.atom` |
| `specweaver.core.loom.atoms.language.atom` | `specweaver.sandbox.language.core.atom` |
| `specweaver.core.loom.atoms.code_structure.atom` | `specweaver.sandbox.code_structure.core.atom` |
| `specweaver.core.loom.atoms.base` | `specweaver.sandbox.base` |
| `specweaver.core.loom.atoms.rule_atom` | `specweaver.sandbox.rule_atom` |

### Layer: `tools/` → `interfaces/`

| Old Import Prefix | New Import Prefix |
|-------------------|-------------------|
| `specweaver.core.loom.tools.git.tool` | `specweaver.sandbox.git.interfaces.tool` |
| `specweaver.core.loom.tools.git.interfaces` | `specweaver.sandbox.git.interfaces.facades` |
| `specweaver.core.loom.tools.git.definitions` | `specweaver.sandbox.git.interfaces.definitions` |
| `specweaver.core.loom.tools.filesystem.tool` | `specweaver.sandbox.filesystem.interfaces.tool` |
| `specweaver.core.loom.tools.filesystem.interfaces` | `specweaver.sandbox.filesystem.interfaces.facades` |
| `specweaver.core.loom.tools.filesystem.models` | `specweaver.sandbox.filesystem.interfaces.models` |
| `specweaver.core.loom.tools.filesystem.definitions` | `specweaver.sandbox.filesystem.interfaces.definitions` |
| `specweaver.core.loom.tools.qa_runner.tool` | `specweaver.sandbox.qa_runner.interfaces.tool` |
| `specweaver.core.loom.tools.qa_runner.interfaces` | `specweaver.sandbox.qa_runner.interfaces.facades` |
| `specweaver.core.loom.tools.qa_runner.definitions` | `specweaver.sandbox.qa_runner.interfaces.definitions` |
| `specweaver.core.loom.tools.mcp.tool` | `specweaver.sandbox.mcp.interfaces.tool` |
| `specweaver.core.loom.tools.mcp.interfaces` | `specweaver.sandbox.mcp.interfaces.facades` |
| `specweaver.core.loom.tools.mcp.definitions` | `specweaver.sandbox.mcp.interfaces.definitions` |
| `specweaver.core.loom.tools.mcp.models` | `specweaver.sandbox.mcp.interfaces.models` |
| `specweaver.core.loom.tools.protocol.tool` | `specweaver.sandbox.protocol.interfaces.tool` |
| `specweaver.core.loom.tools.web.tool` | `specweaver.sandbox.web.interfaces.tool` |
| `specweaver.core.loom.tools.web.interfaces` | `specweaver.sandbox.web.interfaces.facades` |
| `specweaver.core.loom.tools.web.definitions` | `specweaver.sandbox.web.interfaces.definitions` |
| `specweaver.core.loom.tools.code_structure.tool` | `specweaver.sandbox.code_structure.interfaces.tool` |
| `specweaver.core.loom.tools.code_structure.definitions` | `specweaver.sandbox.code_structure.interfaces.definitions` |

### Root-level

| Old Import Prefix | New Import Prefix |
|-------------------|-------------------|
| `specweaver.core.loom.dispatcher` | `specweaver.sandbox.dispatcher` |
| `specweaver.core.loom.security` | `specweaver.sandbox.security` |

## Cross-Domain Dependencies

These sandbox-internal cross-domain imports exist and are ALL lazy (inside functions). This invariant MUST be preserved.

| Source | Target | Reason |
|--------|--------|--------|
| `qa_runner/core/factory.py` | `language/core/{python,ts,rust,kotlin,java}/runner.py` | Factory resolves language-specific runners |
| `code_structure/core/atom.py` | `filesystem/core/executor.py` | Atom uses FileExecutor for file reading |
| `code_structure/core/atom.py` | `language/core/evaluator.py` | Atom uses SchemaEvaluator (lazy) |
| `dispatcher.py` | ALL domains | Orchestrator — legal by design |

> [!WARNING]
> **Constraint**: Cross-domain sandbox imports MUST be lazy (inside functions, not module-level) to prevent circular dependency chains. Document in each domain's root `context.yaml`.

## Proposed Changes

### Commit Boundary 1: Move files + rewrite imports (squashed for CI)

> [!NOTE]
> Locally, work in 2 steps: (1) `git mv` all files, (2) rewrite imports. Squash into a single commit before pushing to keep CI green. Git rename detection still works with `-M` flag.

#### Step 1: File moves via `git mv`

Create the hex directory structure, then move every file:

**Root-level moves:**
- `git mv src/specweaver/core/loom/dispatcher.py src/specweaver/sandbox/dispatcher.py`
- `git mv src/specweaver/core/loom/security.py src/specweaver/sandbox/security.py`
- `git mv src/specweaver/core/loom/atoms/base.py src/specweaver/sandbox/base.py`
- `git mv src/specweaver/core/loom/atoms/rule_atom.py src/specweaver/sandbox/rule_atom.py`

**Per-domain moves** (pattern for each domain):
- `commons/{domain}/*.py` → `sandbox/{domain}/core/`
- `atoms/{domain}/*.py` → `sandbox/{domain}/core/`
- `tools/{domain}/tool.py` → `sandbox/{domain}/interfaces/tool.py`
- `tools/{domain}/interfaces.py` → `sandbox/{domain}/interfaces/facades.py` (RENAMED)
- `tools/{domain}/definitions.py` → `sandbox/{domain}/interfaces/definitions.py`
- `tools/{domain}/models.py` → `sandbox/{domain}/interfaces/models.py` (if exists)

**Special cases:**
- `commons/protocol/interfaces.py` → `sandbox/protocol/core/protocol_interfaces.py` (RENAMED to avoid collision)
- `language/` subdirs (`java/`, `kotlin/`, `python/`, `rust/`, `typescript/`) → `sandbox/language/core/` (preserving subdirectory structure)

**Test directory moves:**
- `tests/unit/core/loom/atoms/{domain}/` → `tests/unit/sandbox/{domain}/core/`
- `tests/unit/core/loom/tools/{domain}/` → `tests/unit/sandbox/{domain}/interfaces/`
- `tests/unit/core/loom/test_dispatcher*.py` → `tests/unit/sandbox/`
- `tests/unit/core/loom/test_security*.py` → `tests/unit/sandbox/`
- `tests/unit/core/loom/test_rule_atom.py` → `tests/unit/sandbox/`
- `tests/integration/core/loom/` → `tests/integration/sandbox/`

#### Step 2: Rewrite all references

**Python files** (`.py`): Apply the Import Path Mapping Table above to ALL occurrences of `specweaver.core.loom` — this includes `import` statements, `from` statements, `@patch()` decorators, and `patch()` context managers.

> [!CAUTION]
> **45+ `@patch()` string literals** exist across test files. These are NOT Python imports — a simple import-based find-replace will miss them. Search for ALL occurrences of the string `specweaver.core.loom` in `.py` files.

> [!WARNING]
> **Files outside the loom test directories also import from `core.loom`** and need import rewrites (but NOT directory moves):
> - `tests/e2e/capabilities/assurance/test_architecture_pipeline.py`
> - `tests/e2e/capabilities/assurance/test_contract_drift_e2e.py`
> - `tests/e2e/capabilities/assurance/test_mcp_flow_e2e.py`
> - `tests/e2e/capabilities/infrastructure/test_ast_tool_injection.py`
> - `tests/e2e/capabilities/infrastructure/test_testrunner_tools_e2e.py`
> - `tests/e2e/flow/test_cpp_flow.py`
> - `tests/unit/core/flow/handlers/test_handlers.py` (7 `@patch()` refs)
> - `tests/unit/assurance/validation/rules/code/test_code_rules_execution.py` (11 `@patch()` refs)
> - `tests/integration/core/flow/engine/test_flow_lineage_integration.py` (2 `@patch()` refs)

**YAML files** (`context.yaml`): Exhaustive list of external context.yaml files requiring updates:

> [!CAUTION]
> `flow/context.yaml` uses SPECIFIC domain paths in `consumes` (e.g., `specweaver/loom/atoms/git`) — NOT just wildcard `loom/*`. These must be rewritten to the correct hex sub-package. Do NOT blindly replace `atoms` → `core` without checking the mapping table.

**`core/flow/context.yaml`** — MOST COMPLEX:
```yaml
# Old:
consumes:
  - specweaver/loom/atoms/git
  - specweaver/loom/atoms/qa_runner
  - specweaver/loom/atoms/code_structure
  - specweaver/loom/atoms/mcp
  - specweaver/loom/dispatcher
  - specweaver/loom/security
forbids:
  - specweaver/loom/tools/*
  - specweaver/loom/commons/*

# New:
consumes:
  - specweaver/sandbox/git/core
  - specweaver/sandbox/qa_runner/core
  - specweaver/sandbox/code_structure/core
  - specweaver/sandbox/mcp/core
  - specweaver/sandbox/dispatcher
  - specweaver/sandbox/security
forbids:
  - specweaver/sandbox/*/interfaces  # Flow must not access agent-facing tools
```

**`src/specweaver/context.yaml`** (root):
- `exposes: loom` → `exposes: sandbox`

**`graph/context.yaml`** (uses dotted notation):
- `allowed_imports: specweaver.core.loom` → `allowed_imports: specweaver.sandbox`

**`workspace/context.yaml`** (uses dotted notation):
- `allowed: src.specweaver.core.loom` → `allowed: src.specweaver.sandbox`

**14 files with `forbids: specweaver/loom/*`** (bulk replace `specweaver/loom/*` → `specweaver/sandbox/*`):
- `workspace/project/context.yaml`
- `workspace/context/context.yaml`
- `workspace/ast/parsers/context.yaml`
- `workspace/ast/adapters/context.yaml`
- `workflows/review/context.yaml`
- `workflows/planning/context.yaml`
- `workflows/drafting/context.yaml`
- `interfaces/cli/context.yaml`
- `interfaces/api/context.yaml`
- `infrastructure/llm/context.yaml`
- `infrastructure/llm/mention_scanner/context.yaml`
- `infrastructure/llm/adapters/context.yaml`
- `core/loom/atoms/context.yaml` (deleted with old tree)
- `core/loom/tools/context.yaml` (deleted with old tree)
- `core/loom/commons/context.yaml` (deleted with old tree)

**tach.toml**: Replace module entry AND rewrite the `[[interfaces]]` expose list:

```toml
# Module entry
{ path = "src.specweaver.sandbox", depends_on = [] },

# Interfaces section — replaces old atoms/commons/tools expose
[[interfaces]]
from = ["src.specweaver.sandbox"]
expose = [
    "dispatcher",
    "security",
    "base",
    "rule_atom",
    "git.core",
    "git.interfaces",
    "filesystem.core",
    "filesystem.interfaces",
    "qa_runner.core",
    "qa_runner.interfaces",
    "mcp.core",
    "mcp.interfaces",
    "protocol.core",
    "protocol.interfaces",
    "web.interfaces",
    "language.core",
    "code_structure.core",
    "code_structure.interfaces",
]
```

#### [NEW] Per-domain `context.yaml` files

**Domain root** (`sandbox/{domain}/context.yaml`) — example for `git`:
```yaml
name: git
level: meta-module
purpose: >
  Git operations — executors, engine atoms, and agent-facing tools.
archetype: orchestrator
consumes: []
```

For domains with cross-domain dependencies, add explicit `consumes`:
```yaml
# sandbox/qa_runner/context.yaml
consumes:
  - specweaver/sandbox/language/core

# sandbox/code_structure/context.yaml
consumes:
  - specweaver/sandbox/filesystem/core
  - specweaver/sandbox/language/core
```

**Hex core** (`sandbox/{domain}/core/context.yaml`):
```yaml
archetype: core
forbids:
  - specweaver/sandbox/{domain}/interfaces
constraints:
  - "Cross-domain sandbox imports MUST be lazy (inside functions)"
```

**Hex interfaces** (`sandbox/{domain}/interfaces/context.yaml`):
```yaml
archetype: orchestrator
consumes:
  - specweaver/sandbox/{domain}/core
```

#### [DELETE] `src/specweaver/core/loom/` — entire directory tree

After all files moved and imports verified, delete the empty tree including all old `context.yaml` files.

### Commit Boundary 2: Documentation + cleanup

#### [MODIFY] Active reference docs (6 files):
- `docs/architecture/architecture_reference.md` — ~30 replacements
- `docs/dev_guides/adding_tools_and_atoms.md` — ~10 replacements
- `docs/dev_guides/layer_isolation_and_di.md` — ~10 replacements
- `docs/dev_guides/mcp_implementation_patterns.md`
- `docs/dev_guides/protocol_analyzers.md`
- `docs/dev_guides/special_patterns_and_adaptations.md`

> [!IMPORTANT]
> **Do NOT update historical implementation plans** for other features (38+ files in `docs/roadmap/features/`). Those documents record decisions made against the old layout and are historical records.

#### [MODIFY] `docs/roadmap/features/topic_07_technical_debt/TECH-01/TECH-01_design.md`
- Update the Progress Tracker: mark SF-3 `Impl Plan ✅`.

### Commit Boundary 3: NFR-6 tech debt issue

#### [NEW] Tech debt issue for NFR-6 (`BaseTool` metaclass registry)
- Add TECH-01b to the technical debt backlog for implementing `BaseTool.__init_subclass__` auto-registration.

## Boundary Violations Resolved by Structural Improvement

These existing violations are silently fixed by the hex restructure:
- `tools/protocol/tool.py` → `atoms/protocol/atom.py` (was: tools forbids atoms) → Now: `interfaces/tool.py` → `core/atom.py` (correct direction)
- `tools/qa_runner/interfaces.py` → `atoms/qa_runner/atom.py` (was: tools forbids atoms) → Now: `interfaces/facades.py` → `core/atom.py` (correct direction)

## Verification Plan

### Validation Script (MANDATORY — run before every commit)

```python
# Run: python .tmp/verify_no_old_paths.py
# Asserts ZERO residual references to old loom paths in src/, tests/, and active docs.
# Scans for: specweaver.core.loom, specweaver/core/loom, specweaver/loom, src.specweaver.core.loom
# Excludes: historical docs in docs/roadmap/features/ (except TECH-01/)
```

### Automated Tests

1. **Smoke test** — `python -c "from specweaver.sandbox.dispatcher import ToolDispatcher"` (verify PEP 420 namespace discovery)
2. **Dispatcher first** — `python -m pytest tests/unit/sandbox/test_dispatcher*.py -x` (single point of failure — verify first)
3. **Full test suite** — `python -m pytest tests/ -x` — NFR-1 Zero Regression, 100% must pass
4. **Boundary check** — `tach check` — verify no violations introduced
5. **Lint check** — `ruff check src/` — no regressions

### Manual Verification

- `sw --help` — CLI boots correctly
- Spot-check: `python -c "from specweaver.sandbox.git.core.executor import GitExecutor"`
- Spot-check: `python -c "from specweaver.sandbox.filesystem.interfaces.facades import create_filesystem_interface"`
