# C-FLOW-06 SF-01 — Context Condensation & Scaffolding

**Status**: APPROVED · **Feature ID**: 3.32d · **FRs owned**: FR-1, FR-4 · **Depends on**: none ·
Design: [C-FLOW-06_design.md](C-FLOW-06_design.md) §Sub-features → SF-01

## Goal

Send non-target context files to the LLM as AST skeletons, so the context window does not saturate
(NFR-1). Write baseline `context.yaml` topologies during `sw init` (FR-4), so project boundaries
exist from the start.

## Changes

1. **[x] Scaffold project** (FR-4) · `src/specweaver/workspace/project/scaffold.py` — Adapter
   (`forbids: loom/*`).
   - `scaffold_project(path: Path)` writes `context.yaml` templates with `pathlib.Path.write_text()`.
   - Do NOT invoke `FileSystemAtom`. Do NOT read `.yaml` files from internal resource paths (pip
     distribution issues).
   - 3 static multi-line Python strings define the default boundaries: (1) Root Project Map,
     (2) `src/` Pure Logic Map, (3) `tests/` Test Map.
2. **Polyglot skeletons** (FR-1) · `src/specweaver/core/loom/commons/language/*/codestructure.py` —
   Execution Logic (tree-sitter bindings).
   - Per language (Python, TS, Java, Kotlin, Rust): `produce_skeleton_string(source_code: bytes) -> str`.
   - Walk the tree-sitter nodes and delete ONLY implementation block bodies (`{ body }` / `def: ...`).
   - **CRITICAL**: keep all docstrings, inline comments and framework decorators (`@RestController`,
     `@pytest`, etc.) — without them the LLM hallucinates intent downstream.
3. **Atom delegation** (FR-1) · `src/specweaver/core/loom/atoms/code_structure/atom.py` —
   Orchestrator (internal sandbox boundary).
   - New intent on the run/query signature: `action="skeletonize"`.
   - Read `target_file` into `bytes` via `EngineFileExecutor`, pass it to the polyglot
     `produce_skeleton_string` dispatcher, return the `str`.
4. **Flow engine wiring** (FR-1) · `src/specweaver/core/flow/handlers/` — Orchestrator (consumes
   `loom/atoms/code_structure`, `llm/PromptBuilder`).
   - In `_validation.py`, `_draft.py`, `_implementation.py`, etc., where `ContextAssembler` fetches
     dependency context: for each non-active entry of `context_files`, run
     `CodeStructureAtom.run(action="skeletonize", target=file)`.
   - Collect the results into a `skeleton_files: dict[str, str]` payload.
5. **PromptBuilder** (FR-1) · `src/specweaver/infrastructure/llm/prompt_builder.py` — Adapter
   (`forbids: loom/*` — no sandbox access).
   - `def add_context()` or the `__init__` kwargs accept a pure dict:
     `skeleton_files: dict[str, str] = None`.
   - `build()` wraps each skeleton in its own `<skeleton_context>` XML block, in order, with no
     sandbox execution or I/O.

## NFR-1 budget

Tree-sitter parses locally in microseconds (C). 50 skeleton files per loop stays well within the
`<1.0s` window.
