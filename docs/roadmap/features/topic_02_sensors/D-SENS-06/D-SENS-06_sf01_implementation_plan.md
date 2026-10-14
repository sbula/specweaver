# Implementation Plan: Structured Code Editing for Agents [SF-01: Rename a symbol in Python]
- **Feature ID**: D-SENS-06
- **Sub-Feature**: SF-01 — Rename a symbol in Python
- **Design Document**: docs/roadmap/features/topic_02_sensors/D-SENS-06/D-SENS-06_design.md
- **Design Section**: §Sub-features → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/D-SENS-06/D-SENS-06_sf01_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-14

**FRs owned**: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6 · **NFRs**: NFR-1 … NFR-6 (Python) ·
**Depends on**: none

## Goal

`rename_symbol(path, symbol_name, new_name)` for Python files. The implementer reaches it through
`CodeStructureTool`; the flow engine through `CodeStructureAtom`. Every proven use changes, or no
file changes.

## Shape

| Piece | Where | Kind |
|---|---|---|
| `find_references(code, name)` | `workspace/ast/parsers/python/_references.py`, on `PythonCodeStructure` | pure logic, one file |
| `plan_rename(files, path, symbol, new_name, parsers)` | `workspace/ast/refactor/rename.py` (new module) | pure logic, many files |
| `project_sources(executor, suffixes, exclusions)`, `apply_changes(executor, plan)` | `sandbox/code_structure/core/changes.py` (new file) | I/O through the `FileExecutor` |
| `rename_symbol` intent | `CodeStructureAtom.run` | engine, no grants |
| `rename_symbol` method | `CodeStructureTool` | agent, `ROLE_INTENTS` + `FolderGrant` |
| executor + exclusions to the tool | `ToolDispatcher._build_registry_kwargs`, `registry.create_ast` | wiring |

The Tool and the Atom are parallel: each reads with `project_sources`, plans with `plan_rename`,
and writes with `apply_changes`. The Tool does not call the Atom for this intent. The dispatcher
hands the Tool the same `FileExecutor` it builds for the Atom, and the scan exclusions
`[agreed 2026-10-14]`.
| `FileExecutor.is_protected(path)` | `sandbox/filesystem/core/executor.py` | public wrapper of `_is_protected` |

### `find_references` — one file, no judgement across files

Returns each occurrence of `name` in the file, sorted by byte, as a small frozen dataclass:
`Reference(kind, line, start_byte, end_byte, receiver)`. Kinds:

| Kind | Python node |
|---|---|
| `definition` | `function_definition` / `class_definition` name |
| `import` | `import_from_statement` name (and its module text), `aliased_import` |
| `bare` | an `identifier` load, with its binding in this file: `bound_here` (the scope that binds it: local, parameter, `for`, `with … as`, `except … as`, comprehension, module assignment, another def) or `free` |
| `attribute` | `attribute` whose attribute is `name`; `receiver` = its object's text (`self`, `Greeter`, `g`, `os.path`) |
| `keyword` | a keyword-argument name — unrelated |
| `string` | a string whose content equals `name` |
| `comment` | a comment containing `name` as a word |
| `scope_escape` | `global name`, `nonlocal name` — always unsure |

Scope rule: a name bound anywhere in a function is local to that whole function; a class body's
bindings do not reach its methods (Python's own rule).

### `plan_rename` — decide proven, unrelated, unsure

Input: `{path: code}` for every Python file of the project, plus text files for mentions.
Output: `RenamePlan(changes: {path: new_code}, mentions: [Spot])` or `RenameRefusal(reason, spots)`.

Steps, in order (each step can refuse; the order puts the cheap checks first):

1. Resolve `symbol_name` with `list_symbols` of `path` (`Class.m` or bare, as `_resolved` does).
   Refuse when it is not listed, or listed twice in the same parent (overload).
2. Check `new_name`: `str.isidentifier()`, not `keyword.iskeyword` / `softkwlist`, not a sibling
   in the same parent.
3. Module path of `path`: from the project root and from `src/` (`a/b.py` → `a.b`,
   `a/__init__.py` → `a`). A relative import resolves against its file.
4. Per file, classify each reference:
   - proven: the definition; an `import` that resolves to the defining module and names the
     symbol, directly or through a module that imports it from there (a re-export in
     `__init__.py`); with `import … as G`, only the imported name changes, not `G`; a `bare` that is `free` in a file that imports it (or is the defining file); an
     `attribute` whose receiver is `self` inside the class or a subclass in the project, the class
     name resolved to it, or a module alias resolved to the defining module;
   - unrelated: a `bare` that is `bound_here` to something else; a `keyword`; an `attribute` whose
     receiver resolves to another module or class;
   - unsure: everything else in code, including `string` and `scope_escape`, and an import of
     the defining module by `*`.
5. A method with the same name in a class above or below it in the project: refuse, "override
   family: SF-02".
6. Any unsure spot → `RenameRefusal`, spots sorted, at most 50 then "+N more" (NFR-3).
7. `new_name` already bound in a file that changes → refuse.
8. Build the new code per file by byte splice of the proven spans, sorted by path (NFR-4).
   Parse each; a new error node → refuse (FR-3, before any write).
9. `comment` references and word matches in text files (`.md .rst .txt .yaml .yml .toml .json
   .cfg .ini`) become `mentions`, same 50 cap.

### `project_sources` — which files

Walks the project root through `executor.list_dir`, never entering a symlink, skipping
`.specweaverignore` matches (`SpecWeaverIgnoreParser`) and the given `exclude_dirs` /
`exclude_patterns`. Returns `{path: code}` for the language's endings and the text files of step 9.

### `apply_changes` — all or none

1. For each changed path, sorted: refuse if `executor.is_protected(path)` (FR-4, both consumers).
2. Re-read each file; refuse if it differs from the content the plan was made from (FR-3).
3. Write each with `executor.write` (atomic per file). Keep the old content.
4. On a failed write: write back every old content, and name each file whose restore failed.
5. No `.tmp.*` file is left (NFR-5): `FileExecutor.write` already removes its own on error.

### The Tool

`rename_symbol` checks, in order: the intent (`_require_intent`); `path` has a write grant; then
`plan_rename` on all project files (trusted read, all files); then every path in `changes` has a
write grant (`MODE_ALLOWS_WRITE`) — else refuse with the count only; spots and mentions in a file
with no read grant are counted, not named (FR-2, FR-5); then `apply_changes`.

## Commit boundaries

### CB-1 — find and plan (pure logic)

- New module `workspace/ast/refactor/` with `context.yaml` (`pure-logic`, consumes
  `workspace/ast/parsers`, forbids `specweaver/sandbox/*`), `tach.toml` module + interface,
  `specweaver.sandbox` gets it in `depends_on`.
- `find_references` on `PythonCodeStructure`; abstract default on `CodeStructureInterface` raises
  `CodeStructureError("rename is not supported for this language")`.
- `"rename"` in Python's `supported_intents` only.
- **Red first**: `tests/unit/workspace/ast/parsers/python/test_python_references.py`,
  `tests/unit/workspace/ast/refactor/test_plan_rename.py`.
- Proves FR-1, FR-2, FR-5 (logic), NFR-3, NFR-4.

### CB-2 — the engine applies it

- `changes.py`, `FileExecutor.is_protected`, `rename_symbol` intent on `CodeStructureAtom`.
- **Red first**: `tests/integration/sandbox/test_rename_through_the_atom.py` over a real tmp
  project and a real `FileExecutor`: rename across 3 files; a protected file in the plan refuses
  and nothing changes; a write that fails midway restores the others (executor wrapper that fails
  on the 2nd write); a file changed after the plan refuses; no `.tmp.` file left; 500 files under
  30 s (NFR-1).
- Proves FR-3, FR-4 (atom half), NFR-1, NFR-5.

### CB-3 — the agent gets it (the seam)

- `ROLE_INTENTS["implementer"]` gets `rename_symbol`; `RENAME_SYMBOL_SCHEMA` in
  `definitions.py` under key `"rename"`; `CodeStructureTool.rename_symbol`.
- **Red first**: `tests/integration/sandbox/test_code_structure_changes_for_an_implementer.py`
  through `ToolDispatcher.create_standard_set(..., role="implementer", allowed_tools=["ast"])`:
  demo steps 1, 2 and 6 of the design; a caller outside the write grants refuses with a count; a
  mention outside the read grants is counted, not named; reviewer, planner, drafter see no
  `rename_symbol` definition; a use inside an ignored `.venv/` does not refuse.
  `test_tool_signatures_match_definitions.py` covers the new method.
- Also: `docs/dev_guides/agent_tools_reference.md` code-structure section; README counts.
- Proves FR-4 (tool half), FR-6, NFR-2.

## Mutants (`D-SENS-06_mutants.json`)

| id | Line neutralised | Must kill |
|---|---|---|
| `unsure-is-proven` | the unsure branch classifies as proven | CB-1 unit, CB-3 demo step 2 |
| `string-ignored` | `string` references skipped | CB-1 unit |
| `bound-here-ignored` | `bound_here` treated as `free` | CB-1 unit |
| `no-parse-guard` | step 8 parse check removed | CB-1 unit |
| `no-restore` | step 4 restore removed | CB-2 integration |
| `no-stale-check` | step 2 re-read removed | CB-2 integration |
| `no-grant-on-callers` | tool checks the grant of `path` only | CB-3 integration |
| `reviewer-can-rename` | `rename_symbol` added to the reviewer | CB-3 integration |

## Research Notes

- `CodeStructureTool` calls `self._atom.run` for every intent today (`interfaces/tool.py:116-255`);
  `grant_mode_for(path, grants, self._atom.cwd)` (`tool.py:313`).
- The dispatcher builds the atom over a plain `FileExecutor(cwd)` (`dispatcher.py:213-221`), so the
  agent side refuses protected files; exclusions are built for the file tool only
  (`dispatcher.py:150-159`, `_build_registry_kwargs`) and must also reach the code-structure tool.
- `get_code_structure_schema(supported_intents, …)` offers a schema only when a parser lists its
  key (`definitions.py:211-236`); `PythonCodeStructure` uses the base default list
  (`interfaces.py:214`).
- `FileExecutor.write` is atomic for one file (`executor.py:161-191`) and cleans its temp file.
- `_resolved` (`atom.py`) already maps a bare method name to its one `Class.name`.
- `extract_supertypes(code)` gives each class's bases (`interfaces.py:164`), for step 4's
  subclass check and step 5.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | How do the Tool and the Atom share the rename? | parallel: shared `changes.py` + `plan_rename`; the Tool does not call the Atom `[agreed 2026-10-14]` |

## Backlog

none
