# Implementation Plan: Context Condensation & Scaffolding [SF-1]
- **Feature ID**: 3.32d
- **Sub-Feature**: SF-1 — Context Condensation & Scaffolding
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-06/C-FLOW-06_design.md
- **Design Section**: §Sub-Feature Breakdown -> SF-1
- **Status**: APPROVED

## 1. Description
Implements AST Skeleton generation via Context Condensation to prevent context-window saturation (NFR-1). Also natively generates `context.yaml` baseline topologies directly during `sw init` scaffolding (FR-4) to immediately ground project boundaries.

## 2. Component Modifications

### [x] A. Scaffold Project (`src/specweaver/workspace/project/scaffold.py`)
- **Archetype**: Adapter (`forbids: loom/*`)
- **FR-4 Implementation**:
  - Update `scaffold_project(path: Path)` to generate native `context.yaml` templates using standard `pathlib.Path.write_text()`. 
  - Do NOT invoke `FileSystemAtom`. Do NOT attempt to read `.yaml` files from internal resource paths (pip distribution issues).
  - Inject 3 static multi-line raw Python strings defining default boundaries for: (1) Root Project Map, (2) `src/` Pure Logic Map, (3) `tests/` Test Map.

### B. Polyglot Code Skeletons (`src/specweaver/core/loom/commons/language/*/codestructure.py`)
- **Archetype**: Execution Logic (Tree-sitter bindings)
- **FR-1 Implementation**:
  - For each language (Python, TS, Java, Kotlin, Rust), add method: `produce_skeleton_string(source_code: bytes) -> str`
  - Ensure the method iterates over tree-sitter nodes mathematically and deletes ONLY implementation block boundaries (`{ body }` / `def: ...`).
  - **CRITICAL**: The string slicing MUST explicitly preserve all docstrings, inline comments, and framework decorators (`@RestController`, `@pytest`, etc.) to prevent LLM intent hallucination downstream.

### C. Atom Delegation (`src/specweaver/core/loom/atoms/code_structure/atom.py`)
- **Archetype**: Orchestrator (Internal sandbox boundary)
- **FR-1 Implementation**:
  - Add a parameter to the run/query signature to route the intent: `action="skeletonize"`
  - Implement execution branch: Read `target_file` completely into `bytes` via `EngineFileExecutor`, pass bytes to the polyglot `produce_skeleton_string` dispatcher, and return the `str`.

### D. Flow Engine Wiring (`src/specweaver/core/flow/handlers/`)
- **Archetype**: Orchestrator (Consumes: `loom/atoms/code_structure`, `llm/PromptBuilder`)
- **FR-1 Implementation**:
  - Within `_validation.py`, `_draft.py`, `_implementation.py`, etc., where `ContextAssembler` fetches background dependency context:
  - Iterate through non-active `context_files`.
  - Execute `CodeStructureAtom.run(action="skeletonize", target=file)`. 
  - Strip the returned strings into a `skeleton_files: dict[str, str]` payload.

### E. PromptBuilder Expansion (`src/specweaver/infrastructure/llm/prompt_builder.py`)
- **Archetype**: Adapter (`forbids: loom/*` — Sandbox access is mathematically illegal).
- **FR-1 Implementation**:
  - Modify `def add_context()` or `__init__` payload kwargs to accept a new pure dictionary: `skeleton_files: dict[str, str] = None`.
  - During `build()`, assemble these skeleton values into distinct `<skeleton_context>` XML wrappers sequentially without performing any sandbox execution or I/O. 

## 3. Backlog & Open Items
- NFR-1 Speed constraints: Tree-sitter runs locally in microseconds directly over C. Processing 50 skeleton files per loop remains heavily within the `<1.0s` window mathematically.
