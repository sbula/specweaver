# Implementation Plan: Structured Code Editing for Agents [SF-04: Create and delete a file; the comment above a symbol]
- **Feature ID**: D-SENS-06
- **Sub-Feature**: SF-04 — Create and delete a file; the comment above a symbol
- **Design Document**: docs/roadmap/features/topic_02_sensors/D-SENS-06/D-SENS-06_design.md
- **Design Section**: §Sub-features → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/D-SENS-06/D-SENS-06_sf04_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-14

**FRs owned**: FR-12, FR-13, FR-14 · **Depends on**: SF-02 (committed); SF-03 (committed `1fc0fd37`)

## Goal

Four intents for the implementer (Tool) and the flow engine (Atom): `create_module(path, code)`,
`delete_module(path)`, `read_symbol_doc(path, symbol_name)` and
`replace_symbol_doc(path, symbol_name, doc)`. With them, and the SF-01 to SF-03 intents, an agent
needs no raw file write.

## Shape

| Piece | Where |
|---|---|
| `plan_create(files, path, code, parser)`, `plan_delete(files, path, parser)` | `workspace/ast/refactor/files.py` (new) |
| `replace_symbol_doc(code, symbol, doc)` per language | `workspace/ast/parsers/_docs.py` (`write_doc`), bound like `_doc_of` |
| the four intents | `CodeStructureAtom.run`; `CodeStructureTool`; schemas; `ROLE_INTENTS["implementer"]` |

### `create_module` (FR-12)

Refuse when: `path` exists, is outside the project or protected, or has no code parser; `code`
does not parse, or parses with an error node. The Tool also needs `FULL` (create) on `path`. The
write goes through `apply_changes` with the path missing from `original`, so an existing file
is never overwritten.

### `delete_module` (FR-13)

Refuse while anything uses the file:

1. every file that imports it: SF-03's `move_edits(path, <a free name beside it>)` lists exactly
   the imports a move would rewrite, so any edit outside the file is an importer;
2. every proven use of one of its top-level symbols in another file (SF-01/02's rename search),
   which covers Go packages, Java's same-package uses and C prototypes in headers;
3. any unsure spot from either search.

The refusal names the files. A Rust module file is always referenced by its parent's `mod` line,
so its delete refuses and names the parent. The Tool also needs `FULL` (delete) on `path`.

### `read_symbol_doc` / `replace_symbol_doc` (FR-14)

`read_symbol_doc` returns `extract_symbol_doc` (markers stripped). `replace_symbol_doc` writes
plain text: the tool adds the markers and the indentation.

| Language | Doc kind | Written as, when there is none yet |
|---|---|---|
| Python | docstring, first statement of the body | `"""text"""`, at the body's indentation |
| Java, Kotlin, TypeScript, C, C++ | comment block directly above | `/** ... */`, one ` * ` line per text line |
| Rust | `///` lines directly above | `/// text` per line |
| Go | `//` lines directly above | `// text` per line |

An existing doc keeps its marker style (`//` stays `//`). An empty `doc` removes the doc. Only the
doc's lines change; the result must parse (SF-01's parse guard). SQL and Markdown refuse.

## Commit boundaries

| CB | Does | Proves |
|---|---|---|
| CB-1 | `create_module`, `delete_module` (planner, Atom, Tool, schemas) | FR-12, FR-13 |
| CB-2 | `read_symbol_doc`, `replace_symbol_doc` in 8 languages (Atom, Tool, schemas) | FR-14 |

Red first: `tests/unit/workspace/ast/refactor/test_plan_files.py`,
`tests/unit/workspace/ast/parsers/test_symbol_doc_round_trip.py` (every language: write, read back,
replace, remove; nothing else changes), and cases in
`tests/integration/sandbox/test_code_structure_changes_for_an_implementer.py` and a new
`tests/integration/sandbox/test_files_through_the_atom.py`.

## Mutants

| id | Line neutralised | Must kill |
|---|---|---|
| `create-overwrites` | the "exists" check | CB-1 unit and integration |
| `create-broken-code` | the parse check on `code` | CB-1 unit |
| `create-grant-off` | the Tool's `FULL` check | CB-1 integration |
| `delete-importers-ignored` | step 1 | CB-1 unit |
| `delete-users-ignored` | step 2 | CB-1 unit |
| `doc-other-lines-touched` | the span of the old doc | CB-2 unit |
| `doc-style-forced` | keeping the existing marker style | CB-2 unit |
| `doc-remove-off` | removing on an empty `doc` | CB-2 unit |

## Research Notes

- `extract_symbol_doc` and `_docs.sibling_doc` / `docstring_doc` already find the doc
  (`_docs.py:101,129`), with `_anchor` for the declaration's outer wrapper and the adjacency rule
  (no blank line between). `write_doc` reuses both to find the span it replaces.
- `apply_changes(executor, original, changes, delete)` already writes new files and deletes, with
  undo (SF-03).
- `MODE_ALLOWS_CREATE`, `MODE_ALLOWS_DELETE` = `{FULL}` (`security.py:35-36`).

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| D1 | What counts as "imported" for a delete | imports, and any proven or unsure use of its symbols from another file (the plan's steps 1–3) `[agreed 2026-10-14]` |
| D2 | Doc markers | the language's usual doc style; an existing doc keeps its own `[agreed 2026-10-14]` |

## Backlog

none
