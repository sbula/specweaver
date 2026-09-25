# D-SENS-02 SF-02 — AST Symbol Writer (Write Side)

**Status**: APPROVED · **FRs owned**: FR-5 · **Depends on**: SF-01 · Design:
[D-SENS-02_design.md](D-SENS-02_design.md) §Sub-features → SF-02

## Goal

Four write intents — `replace_symbol`, `replace_symbol_body`, `add_symbol`, `delete_symbol` —
across the 5 language AST schemas (Python, TS, Java, Kotlin, Rust). An agent edits one symbol on disk
without regex and without loading the whole file into context.

## Where it plugs in

- **Tree-sitter bytes:** every node has `.start_byte` and `.end_byte`. Slice the `utf-8` blob up to
  `start_byte`, insert `new_code`, append the rest from `end_byte` to EOF. No line or indent regex.
- **Persistence:** `CodeStructureAtom` already holds a `FileExecutor`, so it can write the result to
  disk without injecting a tool (which would be a circular dependency).

## Changes

1. **Interface** · `src/specweaver/loom/commons/language/interfaces.py` — on `CodeStructureInterface`:
   - `@abstractmethod def replace_symbol(self, code: str, symbol_name: str, new_code: str) -> str:`
   - `@abstractmethod def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str:`
   - `@abstractmethod def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:`
   - `@abstractmethod def delete_symbol(self, code: str, symbol_name: str) -> str:`
2. **Schemas** · `src/specweaver/loom/tools/code_structure/definitions.py` — add
   `REPLACE_SYMBOL_SCHEMA`, `REPLACE_SYMBOL_BODY_SCHEMA`, `ADD_SYMBOL_SCHEMA`, `DELETE_SYMBOL_SCHEMA`;
   expose them in `get_code_structure_schema()`.
3. **Python parser** · `src/specweaver/loom/commons/language/python/codestructure.py` — the 4
   methods. Find `start_byte`/`end_byte` with the parent-walking logic of `extract_symbol`.
   **Auto-indentation:** for `replace` and `add`, take the target node's `start_point[1]` margin and
   prepend it to every newline in the LLM's `new_code` before the `utf-8` splice — no `IndentationError`.
4. **Other parsers** · `src/specweaver/loom/commons/language/{java,kotlin,rust,typescript}/codestructure.py`
   — the same bounded slice; all 5 parsers find bounds through `name_node.parent`.
5. **Atom** · `src/specweaver/loom/atoms/code_structure/atom.py` — map the 4 intents in `run()`; call
   `parser.<intent>()` for the mutated byte string; write it with `self._executor.write(path, mutated_code)`
   atomically; return `AtomResult(SUCCESS)`.
6. **Tool** · `src/specweaver/loom/tools/code_structure/tool.py` — add the 4 intents to `ROLE_INTENTS`
   for the `implementer` role; route the facade to `self._atom.run()`; pre-flight `.check_grant()`
   against `AccessMode.WRITE` or `AccessMode.FULL`.

## Tests

| File | Case |
|---|---|
| `test_polyglot_ast_edge_cases.py` | `test_write_symbol_python`, `test_write_symbol_typescript`, `test_write_symbol_java`, `test_write_symbol_rust`, `test_write_symbol_kotlin` — exact byte replacement |

Plus the unit and integration suites.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | LLM code arrives with the wrong indentation | Auto-indentation in the parsers |
| Q2 | Atom writes to disk itself? | **Yes — Dual-Consumer Architecture Override**: `CodeStructureAtom` may run `self._executor.write`, an approved exception to the parallel-mechanism isolation rule; the alternative puts heavy complexity in the orchestrator |
| Q3 | One `write_symbol`, or finer actions? | 4 independent actions: `replace_symbol`, `replace_symbol_body`, `add_symbol`, `delete_symbol` |

## As built

- Python first (unit + integration edge cases), then JVM/Rust/TS (75% coverage), then engine
  bindings: all polyglot edge cases and integration boundaries pass the E2E matrix.
- **Since moved** (checked 2026-09-25): the write methods live in
  `src/specweaver/workspace/ast/parsers/` (`interfaces.py`, `_editing.py`); atom and tool in
  `src/specweaver/sandbox/code_structure/`.
