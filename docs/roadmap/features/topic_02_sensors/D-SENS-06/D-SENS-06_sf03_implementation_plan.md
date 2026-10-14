# Implementation Plan: Structured Code Editing for Agents [SF-03: Rename or move a file]
- **Feature ID**: D-SENS-06
- **Sub-Feature**: SF-03 — Rename or move a file
- **Design Document**: docs/roadmap/features/topic_02_sensors/D-SENS-06/D-SENS-06_design.md
- **Design Section**: §Sub-features → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/D-SENS-06/D-SENS-06_sf03_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-14

**FRs owned**: FR-10, FR-11 · **Depends on**: SF-02 (committed `46eb0096`)

## Goal

`move_module(path, new_path)` for the implementer (Tool) and the flow engine (Atom). The file
moves, and every import of it is rewritten, all or none. The SF-01 and SF-02 rules hold: an
import that cannot be resolved for certain is unsure and refuses; a mention in a doc is reported.

## Shape

| Piece | Where |
|---|---|
| `plan_move(files, path, new_path, parser) -> MovePlan \| RenameRefusal` | `workspace/ast/refactor/move.py` (new) |
| per language: which references point at the file, and their new text | a `move_edits` method on each resolver |
| write the new file, apply the edits, delete the old file; undo on failure | `sandbox/code_structure/core/changes.py` `apply_move` |
| `move_module` intent | `CodeStructureAtom.run` |
| `move_module` method, schema `MOVE_MODULE_SCHEMA`, `ROLE_INTENTS["implementer"]` | `sandbox/code_structure/interfaces/` |

`MovePlan` holds `old_path`, `new_path`, `changes` (new content per path, the moved file's
included) and `mentions`.

### Checks, in order (each refuses)

1. `path` exists and has a resolver; `new_path` has the same ending, does not exist, passes the
   executor's path checks, and is not protected.
2. **FR-11:** the nearest folder with a `context.yaml` above `new_path` is the one above `path`.
3. The language's own rule (table below).
4. Every reference that names the file is rewritten; any it cannot rewrite for certain is unsure.
5. Every new content parses; the plan is all or none (SF-01's `_checked`).
6. A doc, spec or config line holding the old path or module name is a mention, reported.
7. The Tool checks the write grant of every changed file, plus `FULL` (create) on `new_path` and
   `FULL` (delete) on `path` (`MODE_ALLOWS_CREATE`, `MODE_ALLOWS_DELETE`).

### Per language

| Language | Rewritten | Refused or unsure |
|---|---|---|
| Python | `from a.b import X`, `import a.b [as c]`, `from a import b`, relative imports in both directions, the module path in `a.b.f()` after a plain `import a.b` | a module path as a string (`importlib`); a package `__init__.py` |
| TypeScript | each relative specifier that resolves to the file, in importers and in the moved file itself | a non-relative specifier when `tsconfig.json` has `paths` or `baseUrl` |
| Go | nothing: a file name means nothing to Go | a move to another folder (FR-10) |
| Java, Kotlin | the `package` line and every `import` of the moved file's types; in Java, the public class named like the file is renamed with the file (FR-10, through SF-02's rename) | a move to another package while files of the old package use its types without an import, or it uses theirs: refused, naming the files `[agreed 2026-10-14]` |
| Rust | the `mod name;` line and every `use` and path segment of the module, in the same folder | a move to another folder `[agreed 2026-10-14]` |
| C, C++ | each quoted `#include` that resolves to the file, recomputed relative to its includer; the moved file's own quoted includes | an include that resolves to more than one file |

## Commit boundaries

| CB | Does | Proves |
|---|---|---|
| CB-1 | `move.py`, `apply_move`, the Atom and Tool intents, schema, FR-11; Python, TypeScript, Go | FR-10 (3 languages), FR-11 |
| CB-2 | Java, Kotlin, Rust, C, C++ | FR-10 |

Each language writes red first: a unit test of its `move_edits`, and one case in
`tests/integration/sandbox/test_code_structure_changes_for_an_implementer.py` through
`ToolDispatcher`. CB-1 also writes `tests/integration/sandbox/test_move_through_the_atom.py`:
a failed write restores every file and leaves the old file in place; a protected target refuses
before any write; a target under another `context.yaml` refuses.

## Mutants (`D-SENS-06_mutants.json`)

| id | Line neutralised | Must kill |
|---|---|---|
| `move-boundary-ignored` | the FR-11 check | CB-1 integration |
| `move-restore-off` | `apply_move`'s undo | CB-1 integration |
| `move-old-file-kept` | the delete of the old path | CB-1 integration |
| `move-target-exists-ok` | the "does not exist" check | CB-1 unit |
| `move-grant-create-off` | the Tool's `FULL` check on `new_path` | CB-1 integration |
| `<lang>-importer-skipped` | one language's importer rewrite | that language's unit test |
| `<lang>-unsure-trusted` | one language's unsure verdict | that language's unit test |

## Research Notes

- `FileExecutor.move(src, dst)` exists (`executor.py:339`) but moves without our edits; the plan
  writes `new_path` with the new content and deletes `path` instead, so one undo covers both.
- `FileExecutor.delete` refuses directories and protected paths (`executor.py:193`).
- `MODE_ALLOWS_CREATE` and `MODE_ALLOWS_DELETE` are `{FULL}` (`security.py:35-36`).
- The resolvers already compute each file's module (`PythonResolver.resolve_module`,
  `TypeScriptResolver.resolve_module`, `RustResolver.module_of`, `GoResolver.package_of`,
  `JvmResolver` package, `CResolver.included`); `move_edits` reuses them.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | Java/Kotlin move to another package with same-package uses | refuse and name the files `[agreed 2026-10-14]` |
| Q2 | Rust move to another folder | refuse; a rename in the same folder works `[agreed 2026-10-14]` |

## Backlog

none
