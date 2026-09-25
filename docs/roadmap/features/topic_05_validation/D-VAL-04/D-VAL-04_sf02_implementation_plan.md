# D-VAL-04 SF-02 — Context Condensation Skeletons

**Status**: ✅ Completed · **FRs owned**: FR-3, FR-4 · **Depends on**: SF-01 · Design:
[D-VAL-04_design.md](D-VAL-04_design.md) §Sub-features → SF-02

## Goal

AST-skeleton condensation before injection, and answering the dependency neighbourhood from the
in-memory graph instead of re-reading files. FRs recorded 2026-08-17 under `specweaver-dev` §3.2c,
from `INT-US-25-SF01-MIG`.

`PromptBuilder` injects context dependencies as AST skeletons to cut token cost without losing
structural context. The `workspace.parsers` AST extractors plug into `PromptBuilder`; a
`skeleton: bool` option on `add_file` and `add_mentioned_files` turns it on. Mentioned files default
to `True` — they are context boundaries, not editing targets.

## Where it plugs in

| Fact | Where |
|---|---|
| `add_file()`, `add_mentioned_files()`, file reads | [prompt_builder.py](file:///c:/development/pitbula/specweaver/src/specweaver/infrastructure/llm/prompt_builder.py) |
| AST extractors (`pure-logic`, so `tach` allows the import) | `workspace.parsers` |

## Changes

1. **Signatures** — `skeleton: bool = False` on `add_file()`; `skeleton: bool = True` on
   `add_mentioned_files()`.
2. **`_extract_skeleton(path: Path, content: str) -> str`** — a pure-logic resolver. Maps the file
   extension to `PythonCodeStructure`, `TypeScriptCodeStructure`, `JavaCodeStructure`,
   `KotlinCodeStructure` or `RustCodeStructure` and runs `.extract_skeleton(content)`.
3. **Integration** — on read, apply `self._extract_skeleton(path, content)` when `skeleton` is
   `True`.

> [!NOTE]
> Parsers are lazy imports inside `PromptBuilder`. On invalid syntax or a tree-sitter failure it
> catches `CodeStructureError` or `Exception` and appends the raw file contents instead, so no data
> is lost.

## Tests

| Where | Case |
|---|---|
| [test_prompt_builder.py](file:///c:/development/pitbula/specweaver/tests/unit/infrastructure/llm/test_prompt_builder.py) | `PromptBuilder.add_file(..., skeleton=True)` calls the parser and returns condensed output with `" ... "` bounds instead of full implementations |
| same | `add_mentioned_files()` defaults to AST compression for external files without affecting priority truncation |

Commands: `pytest tests/unit/infrastructure/llm/ -v`; a full `/pre-commit` (no broken API signatures
or boundaries); `tach check` (no `loom` boundary leak when the LLM builder references AST parsers).

## As built

`_extract_skeleton` lives in its own `_skeleton.py` module, not in `prompt_builder.py`: Ruff caps
a class at 600 lines. Its tests moved to separate modules too.

**Since moved** (noted 2026-09-25): the function is `extract_ast_skeleton` in
`infrastructure/llm/_skeleton.py`; the `skeleton` flags sit in
`infrastructure/llm/prompt/adders.py`;
tests are `test__skeleton.py` and `test_prompt_builder_skeleton.py`.
