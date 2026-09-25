# D-SENS-02 SF-01 — Polyglot AST Extractor

**Status**: COMPLETE · **FRs owned**: FR-1, FR-2, FR-3, FR-4 · **Depends on**: none · Design:
[D-SENS-02_design.md](D-SENS-02_design.md) §Sub-features → SF-01

## Goal

Add **CodeStructureTool** and its backing **AstAtom**, with `read_file_structure` and `read_symbol`.
All language definitions (`.scm` Tree-Sitter queries, AST parsers) live in a consolidated
`loom/commons/language/` registry, so pure-logic consumers stay apart from C-binary I/O.

## Changes

1. **Language commons migration** · `src/specweaver/loom/commons/language/<lang>/` — `qa_runner` is a
   vertical silo; languages become a horizontal commons, one directory level up:
   1. Move `src/specweaver/loom/commons/qa_runner/python/` to
      `src/specweaver/loom/commons/language/python/runner.py`.
   2. Move the other `qa_runner` plugins (TypeScript, Java, Kotlin, Rust) to `language/<lang>/runner.py`.
   3. Point `QARunnerFactory`, `QARunnerAtom` and `QARunnerTool` at `commons/language/`.
   4. Run all tests: `qa_runner` must work identically before going on.
2. **[NEW] AST parsers** · `src/specweaver/loom/commons/language/<lang>/ast_parser.py`, next to the
   runners. `.scm` queries (`@definition.function`, `@definition.class`) inside the file or in adjacent
   `.scm` files. Interface: `extract_skeleton`, `extract_symbol`, `extract_symbol_body`,
   `list_symbols(code, visibility: list[str])`.
3. **[NEW] Atom** (trusted engine I/O, unrestricted, SpecWeaver-internal) ·
   `src/specweaver/loom/atoms/code_structure/atom.py` — `AstAtom(Atom)` with `run_extract_skeleton`,
   `run_extract_symbol`, `run_extract_symbol_body`, `run_list_symbols`. Reads the file through
   `FileExecutor`, dispatches to the language parser, runs the `.scm` query, formats the output.
   Imports only from `commons/language`.
4. **[NEW] Tool** (sandboxed, role-gated, for the LLM):
   - `src/specweaver/loom/tools/code_structure/tool.py` — `CodeStructureTool` with intents
     `read_file_structure`, `read_symbol`, `read_symbol_body`, `list_symbols`. Checks `FolderGrant`
     and `ROLE_INTENTS` before delegating to `AstAtom`.
   - `src/specweaver/loom/tools/code_structure/interfaces.py` — `ReviewerCodeStructureInterface` and
     `ImplementerCodeStructureInterface`: unauthorized intents do not exist on the interface.
   - `src/specweaver/loom/tools/code_structure/definitions.py` — the JSON Schema for the LLM, e.g.
     `"name": "read_file_structure", "description": "Returns only the signatures and docstrings of a file, stripping implementation bodies to save tokens."`
5. **Integration** — `src/specweaver/loom/dispatcher.py` registers `CodeStructureTool` and its
   intents; `src/specweaver/flow/_review.py` & `flow/_generation.py` add it to the Reviewer and
   Implementer toolboxes.

> [!WARNING]
> **Missing SCM queries:** for a file type with no parser (e.g. `.yaml`), `AstAtom` must not fail
> silently or fall back to a full-file read. It raises `CodeStructureError`:
> `"AST Structure Extraction not supported for .yaml files. Please use read_file."`

> [!WARNING]
> **No write side here.** `write_symbol` is SF-02 — patching AST nodes is much harder.

## Tests

| Tier | File | Case |
|---|---|---|
| Unit | `tests/unit/loom/commons/language/python/test_ast.py` | raw Python fixtures → exact signatures and stripped bodies |
| Integration | `tests/integration/loom/tools/code_structure/test_tool.py` | dummy workspace; `read_file_structure` from the tool; JSON output limits; folder-grant enforcement |
| Manual | `sw review` against a dirty spec | the agent picks `read_file_structure` over `read_file` and reads the skeleton without hallucinating the rest of the file |

## As built

**Since moved** (checked 2026-09-25): parsers live in `src/specweaver/workspace/ast/parsers/`; the
atom and tool in `src/specweaver/sandbox/code_structure/` (`core/atom.py`, `interfaces/tool.py`,
`interfaces/definitions.py`).
