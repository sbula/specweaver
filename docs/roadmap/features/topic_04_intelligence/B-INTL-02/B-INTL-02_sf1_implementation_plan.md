# Implementation Plan: Macro & Annotation Evaluator [SF-1: Core Schema Evaluator Engine]
- **Feature ID**: 3.30
- **Sub-Feature**: SF-1 — Core Schema Evaluator Engine
- **Design Document**: docs/roadmap/phase_3/feature_3.30/feature_3.30_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.30/feature_3.30_sf1_implementation_plan.md
- **Status**: APPROVED

## 1. Goal
Implement the `evaluator.py` engine to parse declarative YAML framework schemas and translate raw AST framework markers into LLM-readable runtime explanations. Implement Dependency Injection through the Orchestrator to satisfy architectural limits, and ensure recursive schema security boundaries.

## 2. Research Notes
- **Context.yaml Architecture Restrictions**: As decided in Phase 4, the `evaluator.py` engine residing in `commons/language` cannot dynamically load YAMLs from `workflows/evaluators/`. The top-level Pipeline flow must be responsible for injecting `evaluator_schemas: dict` into the `CodeStructureAtom` runtime.
- **LLM Context Optimization**: Output payloads will not be nested JSON. Evaluator strings MUST be natively prepended as standard line-comments inside the raw source code payload before it is returned by the `read_unrolled_symbol` tool intent.
- **Security**: The parser must be natively pure. `ruamel.yaml` must be executed safely, and no string formatting or `eval()` bindings are allowed against the mappings (NFR-4).
- **Recursion Limits**: The mathematical evaluation dictionary lookup must contain an explicit integer throttle (e.g. `MAX_EVALUATOR_DEPTH = 5`) to prevent Cyclic Mapping OOMs (NFR-5).

## 3. Proposed Changes

### `src/specweaver/core/loom/commons/language/evaluator.py`
#### [NEW]
- Define `class SchemaEvaluator`.
- Constructor accepts `schemas: dict[str, Any]` (which is completely loaded from memory mapping).
- Method `evaluate_markers(language: str, markers: dict) -> str` returns a unified, human-readable paragraph formatted appropriately per language comment style (e.g., `//` for Java/TS, `#` for Python).
- Implements strict `MAX_EVALUATOR_DEPTH = 5` and cyclic tracking `visited = set()` across cascading definitions.

### `src/specweaver/core/loom/atoms/code_structure/atom.py`
#### [MODIFY]
- Update `CodeStructureAtom.__init__` to accept an optional `evaluator_schemas: dict = None`.
- Add internal logic to handle the new `read_unrolled_symbol` intent.
  - 1. Execute `extract_framework_markers()`.
  - 2. Parse against `SchemaEvaluator`.
  - 3. Concatenate the returned explanation block directly above the original output of `extract_symbol()`.

### `src/specweaver/core/loom/tools/code_structure/tool.py`
#### [MODIFY]
- Add the `read_unrolled_symbol` method delegating to the atom's intent. Requires standard file read access bounds.
- Update `ROLE_INTENTS` to whitelist `read_unrolled_symbol` for `implementer` and `reviewer`.

### `src/specweaver/core/loom/tools/code_structure/definitions.py`
#### [MODIFY]
- Define `READ_UNROLLED_SYMBOL_SCHEMA` outlining its semantic advantage over standard reads.

### `src/specweaver/core/flow/_validation.py` (Orchestrator)
#### [MODIFY]
- To resolve FR-4 boundary injection: Load the ecosystem YAML evaluators (via `importlib.resources.files`) natively before dropping down into Executor isolation, directly passing them down as dict kwargs into the underlying tool initialization bounds.
- **[Deviations / Additions in Boundary 2]**: Implemented `load_evaluator_schemas(project_dir)` to natively deep-merge project-local schemas (`.specweaver/evaluators/`) overriding the default ecosystem payloads to fully satisfy FR-4 and NFR-3. Tested thoroughly in integration flow.

## 4. Backlog / Tech Debt
- SF-2 will implement the specific Framework Libraries (Spring Boot, NestJS, etc.), so for now the DI loader should just handle base loading structure without attempting to validate exact definitions.

## 5. Verification Plan
### Automated Tests
1. **`tests/unit/core/loom/commons/language/test_schema_evaluator.py`** [NEW]
   - Verify `MAX_EVALUATOR_DEPTH` halts cascading OOM loops.
   - Verify successful translation of raw marker dicts into language-aware comment blocks.
2. **`tests/integration/core/loom/test_code_structure_tool_evaluator.py`** [NEW]
   - Mock a loaded schema injection and verify `read_unrolled_symbol` cleanly injects comment headers into output blocks without corrupting tree-sitter semantics.
